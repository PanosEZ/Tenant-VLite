import sys, asyncio
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
import zmq
import re
import os
import json

def start_reader():
    context = zmq.Context()
    
    # 1. Look at the sky (Listen for commands from vchat/tenant)
    subscriber = context.socket(zmq.SUB)
    subscriber.connect("tcp://localhost:5555")
    subscriber.setsockopt_string(zmq.SUBSCRIBE, "") 
    
    # 2. Setup the Return Pipe (Send data back to vchat/tenant)
    sender = context.socket(zmq.PUSH)
    sender.connect("tcp://localhost:5556")
    
    print("[Reader] Subscribed to port 5555. Return pipe connected to 5556.")

    command_pattern = re.compile(r"read\(([^)]+)\)")

    while True:
        raw = subscriber.recv_string()

        # PUB messages are now JSON: {"chat_id": "...", "text": "..."}
        try:
            envelope = json.loads(raw)
            message = envelope.get("text", "")
        except (json.JSONDecodeError, AttributeError):
            message = raw
        
        match = command_pattern.search(message)
        if match:
            category = match.group(1).strip()
            # Changed extension to .md based on your terminal logs
            file_name = f"{category}.md" 
            file_path = os.path.join("function-archive", file_name)
            
            if os.path.exists(file_path):
                try:
                    with open(file_path, "r", encoding="utf-8") as file:
                        manual_content = file.read()
                        
                        # --- NEW: Grab the first 100 words and print to terminal ---
                        words = manual_content.split()
                        preview_words = words[:100]
                        preview_text = " ".join(preview_words)
                        
                        # Add an ellipsis if the document is longer than 100 words
                        if len(words) > 100:
                            preview_text += "..."
                            
                        print(f"\n[Reader] Successfully read {file_name}.")
                        print(f"[Reader] Preview (First 100 words):\n{preview_text}\n")
                        # -----------------------------------------------------------
                        
                        # 3. PUSH the text directly back into vchat.py's memory!
                        # We format it nicely so the LLM understands what it's reading.
                        payload = f"SYSTEM TOOL FEEDBACK:\nSuccessfully read {file_name}.\nContent:\n{manual_content}"
                        sender.send_string(payload)
                        
                except Exception as e:
                    error_msg = f"SYSTEM TOOL ERROR: Could not read {file_name}. Error: {e}"
                    print(f"[Reader] {error_msg}")
                    sender.send_string(error_msg)
            else:
                not_found_msg = f"SYSTEM TOOL ERROR: The file {file_name} does not exist."
                print(f"[Reader] {not_found_msg}")
                sender.send_string(not_found_msg)

if __name__ == "__main__":
    start_reader()