import boto3
import zmq
import json


# Hardcoded AWS Credentials
ACCESS_KEY = "AKIAUHTS4K4PUZX7TIBB"
SECRET_KEY = "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"
REGION = "us-east-1"
MODEL_ID = "moonshotai.kimi-k2.5"
TEMPERATURE = 0.3

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
If there is an existing "STORY SO FAR (Diary)", you MUST NOT just report what you just did. Instead, you must rewrite the ENTIRE diary into a single, highly compressed paragraph that combines the most critical old facts with your new findings. The diary should evolve and reshape itself, slowly dropping irrelevant old details while adding current facts.
Example: <CONTEXT>Previously, user asked about verify status. I found 3 unverified users (user1, agent1, user3). Today, user asked for their phone numbers. I looked them up and found none of them have phone numbers provided.</CONTEXT>
Do NOT use the <CONTEXT> tag if you are just chatting and the current state of the user's message does not include the need for the execution of any commands.
"""

# Initialize standard boto3 client
client = boto3.client(
    "bedrock-runtime",
    region_name=REGION,
    aws_access_key_id=ACCESS_KEY,
    aws_secret_access_key=SECRET_KEY
)

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

print("[v-aws] Brain online. Listening for API requests on port 5557...")

MAX_TOOL_ROUNDS = 10  # Safety cap to prevent infinite loops

while True:
    # Wait for a request from a specific api.py client
    identity, request_bytes = api_socket.recv_multipart()
    request = json.loads(request_bytes)
    messages = request.get("messages", [])

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
        # 1. Read the Diary (context.md)
        diary_context = ""
        import os
        if os.path.exists("context.md"):
            with open("context.md", "r") as f:
                diary_context = f.read().strip()
        
        # 2. Dynamically build the System Prompt with the Diary
        dynamic_system_prompt = SYSTEM_PROMPT
        if diary_context:
            dynamic_system_prompt = f"==== STORY SO FAR (Diary) ====\n{diary_context}\n============================\n\n{SYSTEM_PROMPT}"

        # Call AWS Bedrock
        response = client.converse(
            modelId=MODEL_ID,
            messages=messages,
            system=[{"text": dynamic_system_prompt}],
            inferenceConfig={"temperature": TEMPERATURE}
        )

        bot_reply = response['output']['message']['content'][0]['text']
        print(f"\n[TENANT] {bot_reply}")
        print(f"{'-'*60}")

        has_tool = "read(" in bot_reply or "<FUNCTION_CALL>" in bot_reply
        
        # Stream this step immediately back to the client!
        payload = json.dumps({"text": bot_reply, "tool_active": has_tool}).encode()
        api_socket.send_multipart([identity, payload])

        # Add bot reply to conversation for potential follow-up rounds
        messages.append(response['output']['message'])

        # Publish to PUB so reader/executor can see the response
        publisher.send_string(bot_reply)

        # Tool loop — keeps going as long as the LLM triggers a tool
        tool_round = 0
        while has_tool and tool_round < MAX_TOOL_ROUNDS:
            tool_round += 1
            print(f"[v-aws] Tool trigger #{tool_round} detected — waiting for tool result...")
            tool_result = receiver.recv_string()
            print(f"[v-aws] Tool result #{tool_round} received ({len(tool_result)} chars)")

            # Inject the tool result as a user message and call Bedrock again
            messages.append({"role": "user", "content": [{"text": tool_result}]})

            response = client.converse(
                modelId=MODEL_ID,
                messages=messages,
                system=[{"text": dynamic_system_prompt}],
                inferenceConfig={"temperature": TEMPERATURE}
            )
            bot_reply = response['output']['message']['content'][0]['text']
            print(f"\n[TENANT] (follow-up #{tool_round}) {bot_reply}")
            print(f"{'-'*60}")

            has_tool = "read(" in bot_reply or "<FUNCTION_CALL>" in bot_reply
            
            # Stream this follow-up step immediately!
            payload = json.dumps({"text": bot_reply, "tool_active": has_tool}).encode()
            api_socket.send_multipart([identity, payload])

            messages.append(response['output']['message'])

            # Publish the follow-up reply (may trigger another tool round)
            publisher.send_string(bot_reply)

        # Signal completion stream with optimized history
        optimized_history = []
        for msg in messages:
            if msg["role"] == "user":
                text = msg["content"][0]["text"]
                if text.startswith("[Reader] Successfully read"):
                    compressed_text = "[System: Executed read command and internalized manual.]"
                    optimized_history.append({"role": "user", "content": [{"text": compressed_text}]})
                elif text.startswith("[Executor]"):
                    compressed_text = "[System: Executed FUNCTION_CALL and received database results.]"
                    optimized_history.append({"role": "user", "content": [{"text": compressed_text}]})
                else:
                    optimized_history.append(msg)
            else:
                optimized_history.append(msg)

        api_socket.send_multipart([identity, json.dumps({"done": True, "raw_history": optimized_history}).encode()])

    except Exception as e:
        print(f"[v-aws] Error: {e}")
        api_socket.send_multipart([identity, json.dumps({"error": str(e), "done": True}).encode()])