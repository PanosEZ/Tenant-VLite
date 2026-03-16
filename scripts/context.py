import zmq
import re
import datetime
import os
import sys

# Ensure stdout is flushed immediately
sys.stdout.reconfigure(line_buffering=True)

print("[Context] Booting up Context Extraction Service...")

context = zmq.Context()
receiver = context.socket(zmq.SUB)
receiver.connect("tcp://127.0.0.1:5555")
receiver.setsockopt_string(zmq.SUBSCRIBE, "")

CONTEXT_FILE = "context.md"

print("[Context] Subscribed to port 5555. Listening for <CONTEXT> tags...")

while True:
    message = receiver.recv_string()
    
    # Check if the message contains a <CONTEXT> block
    match = re.search(r'<CONTEXT>([\s\S]*?)</CONTEXT>', message)
    if match:
        context_text = match.group(1).strip()
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # Overwrite the context diary file with the new rolling state
        with open(CONTEXT_FILE, "w") as f:
            f.write(context_text + "\n")
            
        print(f"[Context] Updated rolling state: {context_text[:50]}...")
