import os
import sys
import asyncio
import json
import traceback

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

import zmq

script_dir = os.path.dirname(os.path.abspath(__file__))
if script_dir not in sys.path:
    sys.path.insert(0, script_dir)

import re
import subprocess

EXECUTOR_REP_PORT = 5559

MAX_CHAR_LIMIT = 16000

SCRIPT_MAPPING = {
    "account_lookup": "account_lookup.py",
    "lookup_account": "account_lookup.py",  # legacy alias
    "generate_aggregation_report": "aggregation_reporting.py",
    "check_compliance": "compliance_verification.py",
    "traverse_hierarchy": "hierarchy_management.py",
    "check_system_integrity": "system_integrity.py",
}

FUNCTION_CALL_PATTERN = re.compile(r"<FUNCTION_CALL>\s*(.*?)\s*</FUNCTION_CALL>", re.DOTALL)


def _repo_root() -> str:
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def last_function_call_block(text: str) -> str | None:
    matches = list(FUNCTION_CALL_PATTERN.finditer(text))
    if not matches:
        return None
    return matches[-1].group(1).strip()


def run_function_call_json(raw_json_str: str) -> str:
    json_start = raw_json_str.find("{")
    json_end = raw_json_str.rfind("}")
    if json_start == -1 or json_end == -1:
        return "SYSTEM TOOL ERROR: Could not find JSON object in <FUNCTION_CALL> block."
    raw_json_str = raw_json_str[json_start : json_end + 1]
    try:
        payload = json.loads(raw_json_str)
    except json.JSONDecodeError as e:
        return f"SYSTEM TOOL ERROR: Invalid JSON payload. Error: {e}"

    func_name = payload.get("function")
    func_args = payload.get("arguments", {})

    if func_name not in SCRIPT_MAPPING:
        return f"SYSTEM TOOL ERROR: Unknown function '{func_name}'."

    script_name = SCRIPT_MAPPING[func_name]
    script_path = os.path.join(_repo_root(), "executor-archive", script_name)

    if not os.path.exists(script_path):
        return f"SYSTEM TOOL ERROR: The script {script_path} does not exist."

    print(f"[Executor] Running {script_name} with args: {func_args}...")
    try:
        args_json_string = json.dumps(func_args)
        command = [sys.executable, script_path, args_json_string]
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            check=True,
            cwd=_repo_root(),
        )
        db_output = result.stdout.strip()
        output_length = len(db_output)

        if output_length > MAX_CHAR_LIMIT:
            estimated_tokens = output_length // 4
            print(
                f"[Executor] !!! Payload intercepted ({estimated_tokens} est. tokens)"
            )
            return (
                f"SYSTEM COMMAND FAILED: The command you tried to execute for the retrieval of data "
                f"from the database returned an unsustainable amount of data (estimated {estimated_tokens} tokens) "
                f"which crossed the max data limit.\n\n"
                f"Commands like this are forbidden since you cannot handle this much info dump in your context window. "
                f"Try structuring your command differently or using a different command (e.g., utilize 'limit', apply tighter 'filters', "
                f"or narrow down specific 'return_fields'), or inform the user that their request is invalid."
            )

        words = db_output.split()
        preview_text = " ".join(words[:100])
        if len(words) > 100:
            preview_text += "..."
        print(f"[Executor] Success. Preview (first 100 words):\n{preview_text}\n")

        return (
            f"SYSTEM TOOL FEEDBACK:\nSuccessfully executed {func_name}.\nDatabase Output:\n{db_output}"
        )
    except subprocess.CalledProcessError as e:
        error_msg = e.stderr.strip() or e.stdout.strip()
        return f"SYSTEM TOOL ERROR: Script {script_name} crashed. Error: {error_msg}"
    except Exception as e:
        return f"SYSTEM TOOL ERROR: Could not run {func_name}. Error: {str(e)}"


def tool_executor_result(bot_reply: str) -> str | None:
    """Executor script only; None if no <FUNCTION_CALL> in bot_reply."""
    fc_inner = last_function_call_block(bot_reply)
    if not fc_inner:
        return None
    return run_function_call_json(fc_inner)


def start_executor():
    context = zmq.Context()
    socket = context.socket(zmq.REP)
    bind_addr = f"tcp://127.0.0.1:{EXECUTOR_REP_PORT}"
    socket.bind(bind_addr)
    print(
        f"[Executor] REP bound {bind_addr}. <FUNCTION_CALL> → executor-archive scripts. "
        "v-aws sends {{\"bot_reply\": ...}} per tool round."
    )

    while True:
        try:
            raw = socket.recv_string()
            msg = json.loads(raw)
            bot_reply = msg.get("bot_reply", "")
            result = tool_executor_result(bot_reply)
            socket.send_string(json.dumps({"result": result}))
        except Exception as e:
            err = traceback.format_exc()
            print(f"[Executor] Error: {e}\n{err}")
            try:
                socket.send_string(
                    json.dumps({"result": None, "error": str(e)})
                )
            except zmq.ZMQError:
                break


if __name__ == "__main__":
    start_executor()
