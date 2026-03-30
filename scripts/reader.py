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

READER_REP_PORT = 5558
READ_PATTERN = re.compile(r"read\(([^)]+)\)")


def _repo_root() -> str:
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def last_read_category(text: str) -> str | None:
    matches = list(READ_PATTERN.finditer(text))
    if not matches:
        return None
    return matches[-1].group(1).strip()


def run_manual_read(category: str) -> str:
    file_name = f"{category}.md"
    file_path = os.path.join(_repo_root(), "function-archive", file_name)
    if not os.path.exists(file_path):
        return f"SYSTEM TOOL ERROR: The file {file_name} does not exist."
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            manual_content = f.read()
        print(f"[Reader] Read manual {file_name} ({len(manual_content)} chars)")
        return (
            f"SYSTEM TOOL FEEDBACK:\nSuccessfully read {file_name}.\nContent:\n{manual_content}"
        )
    except Exception as e:
        return f"SYSTEM TOOL ERROR: Could not read {file_name}. Error: {e}"


def tool_read_result(bot_reply: str) -> str | None:
    """Manual read only; None if no read(x) in bot_reply."""
    cat = last_read_category(bot_reply)
    if not cat:
        return None
    return run_manual_read(cat)


def start_reader():
    context = zmq.Context()
    socket = context.socket(zmq.REP)
    bind_addr = f"tcp://127.0.0.1:{READER_REP_PORT}"
    socket.bind(bind_addr)
    print(
        f"[Reader] REP bound {bind_addr}. Manual reads (read(x) → function-archive). "
        "v-aws sends {{\"bot_reply\": ...}} per tool round."
    )

    while True:
        try:
            raw = socket.recv_string()
            msg = json.loads(raw)
            bot_reply = msg.get("bot_reply", "")
            result = tool_read_result(bot_reply)
            socket.send_string(json.dumps({"result": result}))
        except Exception as e:
            err = traceback.format_exc()
            print(f"[Reader] Error: {e}\n{err}")
            try:
                socket.send_string(
                    json.dumps({"result": None, "error": str(e)})
                )
            except zmq.ZMQError:
                break


if __name__ == "__main__":
    start_reader()
