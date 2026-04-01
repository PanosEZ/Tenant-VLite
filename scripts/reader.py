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


def user_message_is_manual_read_delivery(text: str) -> bool:
    """True if this user message is the manual content from a prior read() tool round."""
    if not text or not text.strip():
        return False
    if "SYSTEM TOOL FEEDBACK:" in text and "Successfully read" in text:
        return True
    if text.strip().startswith("[Delivered manual content"):
        return True
    return False


def consecutive_read_after_manual_only(messages: list, bot_reply: str) -> bool:
    """
    True when the model is about to run read() again immediately after a read-only
    assistant turn whose tool result was the manual (no intervening <FUNCTION_CALL>).
    messages[-1] must be the assistant message matching bot_reply.
    """
    if "read(" not in bot_reply or len(messages) < 3:
        return False
    if messages[-1].get("role") != "assistant":
        return False
    prev_user = messages[-2]
    prev_asst = messages[-3]
    if prev_user.get("role") != "user" or prev_asst.get("role") != "assistant":
        return False
    prev_asst_text = prev_asst["content"][0].get("text", "")
    if "read(" not in prev_asst_text or "<FUNCTION_CALL>" in prev_asst_text:
        return False
    prev_user_text = prev_user["content"][0].get("text", "")
    return user_message_is_manual_read_delivery(prev_user_text)


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
