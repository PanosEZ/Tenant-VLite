import sys, asyncio
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
import zmq
import re
import json
import os
import sys

sys.stdout.reconfigure(line_buffering=True)

print("[Context] Booting up Context Extraction Service...")

HISTORY_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "history")
os.makedirs(HISTORY_DIR, exist_ok=True)

zmq_context = zmq.Context()
receiver = zmq_context.socket(zmq.SUB)
receiver.connect("tcp://127.0.0.1:5555")
receiver.setsockopt_string(zmq.SUBSCRIBE, "")

print("[Context] Subscribed to port 5555. Listening for <CONTEXT> tags...")

while True:
    raw = receiver.recv_string()

    # PUB messages are now JSON: {"chat_id": "...", "text": "..."}
    try:
        envelope = json.loads(raw)
        chat_id = envelope.get("chat_id", "")
        message = envelope.get("text", "")
    except (json.JSONDecodeError, AttributeError):
        continue

    match = re.search(r'<CONTEXT>([\s\S]*?)</CONTEXT>', message)
    if match and chat_id:
        context_text = match.group(1).strip()
        chat_path = os.path.join(HISTORY_DIR, f"{chat_id}.json")

        # Read existing chat JSON, update context_diary, write back
        try:
            if os.path.exists(chat_path):
                with open(chat_path, "r", encoding="utf-8") as f:
                    chat_data = json.load(f)
            else:
                chat_data = {"id": chat_id, "messages": [], "title": ""}

            chat_data["context_diary"] = context_text

            with open(chat_path, "w", encoding="utf-8") as f:
                json.dump(chat_data, f, ensure_ascii=False, indent=4)

            print(f"[Context] Saved diary to {chat_id}: {context_text[:50]}...")
        except Exception as e:
            print(f"[Context] Error saving diary for {chat_id}: {e}")
