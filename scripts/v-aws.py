import boto3
from botocore.config import Config
import sys, asyncio, time
import zmq
import json
import re
import os




if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())


script_dir = os.path.dirname(os.path.abspath(__file__))
creds_path = os.path.join(script_dir, 'aws_credentials.json')

REGION = "us-east-1"
MODEL_ID = "moonshotai.kimi-k2.5"
TEMPERATURE = 0.3

# Hot-reloadable boto3 client: rebuilds automatically when aws_credentials.json changes
_client = None
_creds_mtime = 0
_last_used = 0
IDLE_TIMEOUT = 180  # seconds — force new connection after 3 min idle

def get_client():
    """Return a boto3 Bedrock client, rebuilding it if the credentials file changed
    or the connection has been idle too long (prevents stale TCP connections)."""
    global _client, _creds_mtime, _last_used

    now = time.time()
    try:
        current_mtime = os.path.getmtime(creds_path)
    except OSError:
        current_mtime = 0

    idle_too_long = _last_used > 0 and (now - _last_used) > IDLE_TIMEOUT

    if _client is not None and current_mtime == _creds_mtime and not idle_too_long:
        _last_used = now
        return _client

    if idle_too_long:
        print(f"[v-aws] Connection idle for {int(now - _last_used)}s — rebuilding client to avoid stale TCP.")

    access_key = ""
    secret_key = ""
    if os.path.exists(creds_path):
        with open(creds_path, 'r') as f:
            creds = json.load(f)
            access_key = creds.get("AWS_ACCESS_KEY_ID", "")
            secret_key = creds.get("AWS_SECRET_ACCESS_KEY", "")
        print(f"[v-aws] Loaded credentials from {creds_path}")
    else:
        print(f"[v-aws] WARNING: {creds_path} not found.")

    _client = boto3.client(
        "bedrock-runtime",
        region_name=REGION,
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key,
        config=Config(
            connect_timeout=5,
            read_timeout=60,
            retries={"max_attempts": 3, "mode": "standard"},
            tcp_keepalive=True
        )
    )
    _creds_mtime = current_mtime
    _last_used = now
    return _client


SYSTEM_PROMPT = """
You are Tenant (just a name), a service QA employee for a user management platform. You have access to a live database of accounts (users, agents, admins) via the <INIT> tool guide. You can look up profiles, trace hierarchies, run reports, and check compliance — never guess or fabricate data.

You have access to the following ability function related commands:
account_lookup class type functions
hierarchy_management class type functions
aggregation_reporting class type functions
compliance_verification class type fuctions
system_integrity class type functions

Classify the user's messages and decide if its a generic chat convo or a specific platform request.
If its a platform type request, it has to adhere to being specific to the class categories. Even if its a platform specific request, if its not related to something of the categories then you should inform/ask the user to specify what about the platform specifically.

If you decide the user is making a clear request, use the command "read(x)" where x should be replaced by the class category related to the request. The category should be only 1 out of the 5 that is provided by the system.
The read command allows you to read the contents of the manual of the category you selected to understand how to use the functions related to that category.

CRITICAL RULE FOR USING COMMANDS: 
When you decide to use the read(x) command, you MUST always speak to the user naturally on the first line, and then place the read(x) command on a new, separate line below it.
Example format:
Let me pull up the manual to find the exact function for that.
read(account_lookup)

CRITICAL RULE FOR LONG TERM MEMORY ("DIARY"):
When you finally answer the user's request after executing command(s) (i.e. you have completed a workflow and are providing the final answer), you MUST write a single, rolling summary paragraph wrapped in <CONTEXT>...</CONTEXT> tags.

HOW TO WRITE THE DIARY:
Rewrite the ENTIRE existing diary into a single, highly compressed paragraph wrapped in <CONTEXT>...</CONTEXT>.
Write the diary constructively and not destructively, i.e. do not remove the previous diary content. Instead, merge the new learnings to the existing diary content.
use natural converstation filler when writing the diary.
do not keep facts like names, dates, numbers, etc. Keep the logic , mechanics and patterns only.
use natural language to describe what you learned about the logic and mechanics of the systemand how it may help you later.
strictly preserve learned patterns, successful logic flows, discovered system constraints, and persisting mechanics about how the system works that may help you in the future.
Your goal is to maintain an evolving understanding of the system's workflow and logic. Do NOT use the <CONTEXT> tag for purely conversational turns where no commands were executed.
the diary should not be longer than 300 words.
STRICTLY never store attributes in the diary. store only behaviors on a conceptual level. store functional concepts and not direct database information.

"""

# --- ZMQ Setup ---
context = zmq.Context()

# PUB socket for reader.py and executor.py to observe
publisher = context.socket(zmq.PUB)
publisher.bind("tcp://*:5555")

# PULL socket to receive tool results from reader.py / executor.py
receiver = context.socket(zmq.PULL)
receiver.bind("tcp://*:5556")

# ROUTER socket to receive chat requests from api.py and reply streamingly
api_socket = context.socket(zmq.ROUTER)
api_socket.bind("tcp://*:5557")

def sanitize_messages(messages):
    """Ensure no message has a blank text field, which Bedrock rejects."""
    for msg in messages:
        if isinstance(msg.get("content"), list):
            for block in msg["content"]:
                if "text" in block and not block["text"].strip():
                    block["text"] = "(continued)"

def truncate_at_tool(text):
    """When the model triggers a tool command, strip any hallucinated content
    it generated after the command. Returns text up to and including the tool line."""
    # Find the end position of a read(x) line
    read_match = re.search(r'^.*read\([^)]+\).*$', text, re.MULTILINE)
    read_end = read_match.end() if read_match else None

    # Find the end position of a </FUNCTION_CALL> block
    func_match = re.search(r'</FUNCTION_CALL>', text)
    func_end = func_match.end() if func_match else None

    # Pick whichever tool command appears first
    candidates = [pos for pos in (read_end, func_end) if pos is not None]
    if not candidates:
        return text
    cut_pos = min(candidates)
    return text[:cut_pos]

print("[v-aws] Brain online. Listening for API requests on port 5557...")

HISTORY_DIR = os.path.join(os.path.dirname(script_dir), "history")
MAX_TOOL_ROUNDS = 10  # Safety cap to prevent infinite loops

while True:
    # Wait for a request from a specific api.py client
    identity, request_bytes = api_socket.recv_multipart()
    request = json.loads(request_bytes)
    messages = request.get("messages", [])
    chat_id = request.get("chat_id", "")

    if not messages:
        api_socket.send_multipart([identity, json.dumps({"error": "No messages provided", "done": True}).encode()])
        continue

    # Print the user's latest message
    last_user_msg = messages[-1].get("content", [{}])
    if isinstance(last_user_msg, list) and last_user_msg:
        user_text = last_user_msg[0].get("text", "")
    else:
        user_text = str(last_user_msg)
    print(f"\n{'='*60}")
    print(f"[USER] {user_text}")
    print(f"{'='*60}")

    try:
        # 1. Read the Diary from this chat's history JSON
        diary_context = ""
        if chat_id:
            chat_path = os.path.join(HISTORY_DIR, f"{chat_id}.json")
            if os.path.exists(chat_path):
                try:
                    with open(chat_path, "r", encoding="utf-8") as f:
                        chat_data = json.load(f)
                    diary_context = chat_data.get("context_diary", "")
                except Exception:
                    pass
        
        # 2. Dynamically build the System Prompt with the Diary
        dynamic_system_prompt = SYSTEM_PROMPT
        if diary_context:
            dynamic_system_prompt = f"==== STORY SO FAR (Diary) ====\n{diary_context}\n============================\n\n{SYSTEM_PROMPT}"

        # Call AWS Bedrock (client reloads creds automatically if file changed)
        sanitize_messages(messages)
        response = get_client().converse(
            modelId=MODEL_ID,
            messages=messages,
            system=[{"text": dynamic_system_prompt}],
            inferenceConfig={"temperature": TEMPERATURE}
        )

        bot_reply = response['output']['message']['content'][0]['text']
        usage = response.get('usage', {})
        total_tokens = usage.get('inputTokens', 0) + usage.get('outputTokens', 0)
        print(f"\n[TENANT] {bot_reply}")
        print(f"[TOKENS] {total_tokens} (in={usage.get('inputTokens',0)} out={usage.get('outputTokens',0)})")
        print(f"{'-'*60}")

        has_tool = "read(" in bot_reply or "<FUNCTION_CALL>" in bot_reply
        
        # When a tool is triggered, truncate hallucinated content after the command
        display_text = truncate_at_tool(bot_reply) if has_tool else bot_reply

        # Stream the clean text to the client
        payload = json.dumps({"text": display_text, "tool_active": has_tool}).encode()
        api_socket.send_multipart([identity, payload])

        # If a tool was triggered, signal the frontend to finalize this bubble
        if has_tool:
            api_socket.send_multipart([identity, json.dumps({"chain_step": True}).encode()])

        # Add the truncated reply to conversation history so the model doesn't see its own hallucinations
        messages.append({"role": "assistant", "content": [{"text": display_text}]})

        # Publish to PUB so reader/executor/context can see the tool commands
        publisher.send_string(json.dumps({"chat_id": chat_id, "text": bot_reply}))

        # Tool loop — keeps going as long as the LLM triggers a tool
        tool_round = 0
        while has_tool and tool_round < MAX_TOOL_ROUNDS:
            tool_round += 1
            print(f"[v-aws] Tool trigger #{tool_round} detected — waiting for tool result...")
            tool_result = receiver.recv_string()
            print(f"[v-aws] Tool result #{tool_round} received ({len(tool_result)} chars)")

            # Inject the tool result as a user message and call Bedrock again
            messages.append({"role": "user", "content": [{"text": tool_result}]})

            sanitize_messages(messages)
            response = get_client().converse(
                modelId=MODEL_ID,
                messages=messages,
                system=[{"text": dynamic_system_prompt}],
                inferenceConfig={"temperature": TEMPERATURE}
            )
            bot_reply = response['output']['message']['content'][0]['text']
            round_usage = response.get('usage', {})
            total_tokens += round_usage.get('inputTokens', 0) + round_usage.get('outputTokens', 0)
            print(f"\n[TENANT] (follow-up #{tool_round}) {bot_reply}")
            print(f"[TOKENS] cumulative={total_tokens} (this round: in={round_usage.get('inputTokens',0)} out={round_usage.get('outputTokens',0)})")
            print(f"{'-'*60}")

            has_tool = "read(" in bot_reply or "<FUNCTION_CALL>" in bot_reply
            
            # When a tool is triggered, truncate hallucinated content after the command
            display_text = truncate_at_tool(bot_reply) if has_tool else bot_reply

            # Stream the clean text to the client
            payload = json.dumps({"text": display_text, "tool_active": has_tool}).encode()
            api_socket.send_multipart([identity, payload])

            # If a tool was triggered, signal the frontend to finalize this bubble
            if has_tool:
                api_socket.send_multipart([identity, json.dumps({"chain_step": True}).encode()])

            # Add the truncated reply to conversation history
            messages.append({"role": "assistant", "content": [{"text": display_text}]})

            # The tool result (messages[-2]) has now been consumed by the model.
            # Replace it with a short summary so it doesn't bloat subsequent calls.
            if len(messages) >= 2 and messages[-2]["role"] == "user":
                prev_text = messages[-2]["content"][0]["text"]
                if prev_text.startswith("SYSTEM TOOL FEEDBACK:"):
                    lines = prev_text.split('\n')
                    summary = lines[1].strip() if len(lines) > 1 else "tool result"
                    messages[-2]["content"][0]["text"] = f"[Delivered — {summary}]"
                    print(f"[v-aws] Compressed consumed tool result: {summary}")

            # Publish full text so reader/executor can detect tool commands
            publisher.send_string(json.dumps({"chat_id": chat_id, "text": bot_reply}))

        done_payload = {"done": True, "total_tokens": total_tokens}
        api_socket.send_multipart([identity, json.dumps(done_payload).encode()])

    except Exception as e:
        print(f"[v-aws] Error: {e}")
        api_socket.send_multipart([identity, json.dumps({"error": str(e), "done": True}).encode()])