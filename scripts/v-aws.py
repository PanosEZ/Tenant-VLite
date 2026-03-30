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
if script_dir not in sys.path:
    sys.path.insert(0, script_dir)

READER_REP_PORT = 5558
EXECUTOR_REP_PORT = 5559


def merge_tool_results(read_result, exec_result):
    """Same join order as before: read first, then function execution."""
    parts = []
    if read_result:
        parts.append(read_result)
    if exec_result:
        parts.append(exec_result)
    if not parts:
        return None
    if len(parts) == 1:
        return parts[0]
    return (
        "\n\n--- NEXT TOOL RESULT (same turn; read first, then execution) ---\n\n".join(
            parts
        )
    )

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
You are Tenant (just a name), a service QA employee for the Tenant AI user management platform. You have access to a live database of accounts from the Tenant Platform in real time (users, agents, admins) via the tool guide. You can look up profiles, trace hierarchies, run reports, and check compliance — never guess or fabricate data.

You have access to the following categories of functions:

* account_lookup
* hierarchy_management
* aggregation_reporting
* compliance_verification
* system_integrity

Classify the user's messages and decide if its a generic chat convo or a specific platform request.

When the user is making a request related to the platform, use the command "read(x)" where x should be replaced by the class category name related to the request. The category should be only 1 out of the 5 that is provided by the system.
The read command allows you to read the contents of the manual of the category you selected to understand how to use the functions related to that category.
STRICTLY ALWAYS USE THE COMMAND OR 'read' when the user is making a platform request , do not dare to make up and give nonsense information user that you didnt fetch from the Platform's system.
important: striclty avoid repeated read(x) commands unless absolutely necessary. strictly follow the chain of read-function-read-funtion and so on. you are only allowed to use the pattern like read-read ... only if the first read provided info that is not relevant with your case.

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
do not keep facts like names, dates, numbers, etc. Keep the only strictly the abstract conceptual logic, mechanics and patterns only.
use natural language to describe what you learned about the logic and mechanics of the system and how it may help you later.
strictly preserve learned patterns and high level concepts, successful logic flows, discovered system constraints, and persisting mechanics about how the system works that may help you in the future.
Your goal is to maintain an evolving understanding of the system's workflow and logic conceptually. Do NOT use the <CONTEXT> tag for purely conversational turns where no commands were executed.
the diary should not be longer than 200 words.
STRICTLY never store attributes in the diary. store only behaviors on a conceptual level. store functional concepts and not direct database information.

"""

# --- ZMQ Setup ---
context = zmq.Context()

# PUB socket for context.py (<CONTEXT> diary extraction)
publisher = context.socket(zmq.PUB)
publisher.bind("tcp://*:5555")

# Tool execution: reader.py (REP on READER_REP_PORT) + executor.py (REP on EXECUTOR_REP_PORT).
# v-aws only merges RPC results — no subprocess/manual reads here.

TOOL_RPC_TIMEOUT_MS = 300_000  # 5 min per worker (long DB queries)


def fetch_tool_results_from_workers(bot_reply: str):
    """Ask reader then executor workers; merge in the same order as tools_inline."""
    payload = json.dumps({"bot_reply": bot_reply})

    def one_rpc(port: int):
        s = context.socket(zmq.REQ)
        s.setsockopt(zmq.LINGER, 0)
        s.setsockopt(zmq.RCVTIMEO, TOOL_RPC_TIMEOUT_MS)
        s.connect(f"tcp://127.0.0.1:{port}")
        try:
            s.send_string(payload)
            return json.loads(s.recv_string())
        except zmq.Again:
            return {"result": None, "error": "RPC timeout (worker not running or hung)"}
        finally:
            s.close()

    r_ack = one_rpc(READER_REP_PORT)
    e_ack = one_rpc(EXECUTOR_REP_PORT)

    read_part = None
    if r_ack.get("error"):
        read_part = f"SYSTEM TOOL ERROR (reader): {r_ack['error']}"
    else:
        read_part = r_ack.get("result")

    exec_part = None
    if e_ack.get("error"):
        exec_part = f"SYSTEM TOOL ERROR (executor): {e_ack['error']}"
    else:
        exec_part = e_ack.get("result")

    return merge_tool_results(read_part, exec_part)


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
    """Strip hallucinated content after the last tool command in this message."""
    read_matches = list(re.finditer(r"^.*read\([^)]+\).*$", text, re.MULTILINE))
    read_end = read_matches[-1].end() if read_matches else None

    func_match = re.search(r"</FUNCTION_CALL>", text)
    func_end = func_match.end() if func_match else None

    candidates = [pos for pos in (read_end, func_end) if pos is not None]
    if not candidates:
        return text
    cut_pos = max(candidates)
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
    model_id = request.get("model_id") or MODEL_ID

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
            modelId=model_id,
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

        # Publish for context.py (<CONTEXT> diary extraction).
        publisher.send_string(json.dumps({"chat_id": chat_id, "text": bot_reply}))

        # Tool loop — keeps going as long as the LLM triggers a tool
        tool_round = 0
        while has_tool and tool_round < MAX_TOOL_ROUNDS:
            tool_round += 1
            print(f"[v-aws] Tool trigger #{tool_round} — RPC reader + executor...")
            tool_result = fetch_tool_results_from_workers(bot_reply)
            if tool_result is None:
                tool_result = (
                    "SYSTEM TOOL ERROR: Model output indicated a tool but no valid read(x) or "
                    "<FUNCTION_CALL>...</FUNCTION_CALL> could be executed."
                )
            else:
                print(f"[v-aws] Tool result #{tool_round} ({len(tool_result)} chars)")

            # Inject the tool result as a user message and call Bedrock again
            messages.append({"role": "user", "content": [{"text": tool_result}]})

            sanitize_messages(messages)
            response = get_client().converse(
                modelId=model_id,
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

            publisher.send_string(json.dumps({"chat_id": chat_id, "text": bot_reply}))

        done_payload = {"done": True, "total_tokens": total_tokens}
        api_socket.send_multipart([identity, json.dumps(done_payload).encode()])

    except Exception as e:
        print(f"[v-aws] Error: {e}")
        api_socket.send_multipart([identity, json.dumps({"error": str(e), "done": True}).encode()])