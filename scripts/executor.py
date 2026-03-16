import sys, asyncio
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
import zmq
import re
import os
import sys
import subprocess
import json

# --- CONFIGURATION ---
# 1 token is roughly 4 characters. 16,000 chars is ~4,000 tokens.
# Adjust this threshold based on your LLM's context window limits.
MAX_CHAR_LIMIT = 16000 

def start_executor():
    context = zmq.Context()
    
    # 1. Listen to the sky
    subscriber = context.socket(zmq.SUB)
    subscriber.connect("tcp://localhost:5555")
    subscriber.setsockopt_string(zmq.SUBSCRIBE, "") 
    
    # 2. Return Pipe
    sender = context.socket(zmq.PUSH)
    sender.connect("tcp://localhost:5556")
    
    print("[Executor] Subscribed to port 5555. Return pipe connected to 5556.")

    # 3. Multiline Regex to catch the exact <FUNCTION_CALL> block
    command_pattern = re.compile(r"<FUNCTION_CALL>\s*(.*?)\s*</FUNCTION_CALL>", re.DOTALL)

    # 4. Map the JSON function names to your actual python scripts
    script_mapping = {
        "lookup_account": "account_lookup.py",
        "generate_aggregation_report": "aggregation_reporting.py",
        "check_compliance": "compliance_verification.py",
        "traverse_hierarchy": "hierarchy_management.py",
        "check_system_integrity": "system_integrity.py"
    }

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
            raw_json_str = match.group(1).strip()
            print(f"\n[Executor] - Detected <FUNCTION_CALL>!")
            
            # Extract just the JSON object from the matched section
            json_start = raw_json_str.find('{')
            json_end = raw_json_str.rfind('}')
            if json_start != -1 and json_end != -1:
                raw_json_str = raw_json_str[json_start:json_end+1]
            
            try:
                # Parse the JSON payload
                payload = json.loads(raw_json_str)
                func_name = payload.get("function")
                func_args = payload.get("arguments", {})
                
                # Look up which script to run
                if func_name not in script_mapping:
                    error_msg = f"SYSTEM TOOL ERROR: Unknown function '{func_name}'."
                    sender.send_string(error_msg)
                    print(f"[Executor] X {error_msg}")
                    continue
                    
                script_name = script_mapping[func_name]
                script_path = os.path.join("executor-archive", script_name)
                
                if os.path.exists(script_path):
                    print(f"[Executor] Running {script_name} with args: {func_args}...")
                    
                    # 5. Execute the script and pass the arguments as a single JSON string
                    args_json_string = json.dumps(func_args)
                    command = [sys.executable, script_path, args_json_string]
                    
                    result = subprocess.run(command, capture_output=True, text=True, check=True)
                    db_output = result.stdout.strip()
                    
                    output_length = len(db_output)
                    
                    # ==========================================
                    # THE CIRCUIT BREAKER (PAYLOAD INTERCEPTOR)
                    # ==========================================
                    if output_length > MAX_CHAR_LIMIT:
                        estimated_tokens = output_length // 4
                        print(f"[Executor] !!! WARNING: Catastrophic payload intercepted! ({estimated_tokens} tokens)")
                        
                        # Replace the massive database output with a strict system instruction
                        error_instruction = (
                            f"SYSTEM COMMAND FAILED: The command you tried to execute for the retrieval of data "
                            f"from the database returned an unsustainable amount of data (estimated {estimated_tokens} tokens) "
                            f"which crossed the max data limit.\n\n"
                            f"Commands like this are forbidden since you cannot handle this much info dump in your context window. "
                            f"Try structuring your command differently or using a different command (e.g., utilize 'limit', apply tighter 'filters', "
                            f"or narrow down specific 'return_fields'), or inform the user that their request is invalid."
                        )
                        
                        return_payload = error_instruction
                    else:
                        # Payload is safe, proceed normally
                        return_payload = f"SYSTEM TOOL FEEDBACK:\nSuccessfully executed {func_name}.\nDatabase Output:\n{db_output}"
                    # ==========================================

                    # Extract first 100 words of the database output for terminal debug
                    words = db_output.split()
                    preview_text = " ".join(words[:100])
                    if len(words) > 100:
                        preview_text += "..."
                    
                    # 6. PUSH the database results back to vchat.py
                    sender.send_string(return_payload)
                    
                    if output_length <= MAX_CHAR_LIMIT:
                        print(f"[Executor] Success! Sent database results back to Tenant.")
                        print(f"[Executor] Preview (First 100 words):\n{preview_text}\n")
                    
                else:
                    sender.send_string(f"SYSTEM TOOL ERROR: The script {script_path} does not exist.")
                    print(f"[Executor] !!! Missing script: {script_path}")

            except json.JSONDecodeError as e:
                sender.send_string(f"SYSTEM TOOL ERROR: Invalid JSON payload. Error: {e}")
                print(f"[Executor] X JSON Parse Error: {e}")
            except subprocess.CalledProcessError as e:
                error_msg = e.stderr.strip() or e.stdout.strip()
                sender.send_string(f"SYSTEM TOOL ERROR: Script {script_name} crashed. Error: {error_msg}")
                print(f"[Executor] X Script crashed: {error_msg}")
            except Exception as e:
                sender.send_string(f"SYSTEM TOOL ERROR: Could not run {func_name}. Error: {str(e)}")

if __name__ == "__main__":
    start_executor()