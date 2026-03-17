import os
import json
import time
import asyncio
import sys
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
import zmq
import zmq.asyncio
from fastapi import FastAPI, Request
from fastapi.responses import StreamingResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
MODEL_ID = "moonshotai.kimi-k2.5"
HISTORY_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "history")
os.makedirs(HISTORY_DIR, exist_ok=True)

# ---------------------------------------------------------------------------
# ZMQ — async context for talking to v-aws.py
# ---------------------------------------------------------------------------
zmq_ctx = zmq.asyncio.Context()

# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------
app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Model endpoint
# ---------------------------------------------------------------------------
@app.get("/model")
async def get_model():
    return {"name": MODEL_ID}

# ---------------------------------------------------------------------------
# Chat history endpoints
# ---------------------------------------------------------------------------
@app.get("/history/list")
async def history_list():
    chats = []
    if not os.path.isdir(HISTORY_DIR):
        return JSONResponse([])
    for fname in os.listdir(HISTORY_DIR):
        if not fname.endswith(".json"):
            continue
        fpath = os.path.join(HISTORY_DIR, fname)
        try:
            with open(fpath, "r", encoding="utf-8") as f:
                data = json.load(f)
            # Build a preview from the first user message
            preview = ""
            for msg in data.get("messages", []):
                if msg.get("role") == "user":
                    preview = msg["content"][0]["text"][:80]
                    break
            chats.append({
                "id": data.get("id", fname.replace(".json", "")),
                "title": data.get("title", ""),
                "preview": preview,
                "updatedAt": data.get("updatedAt", ""),
            })
        except Exception:
            continue
    # Sort newest first
    chats.sort(key=lambda c: c.get("updatedAt", ""), reverse=True)
    return JSONResponse(chats)


@app.get("/history/{chat_id}")
async def history_get(chat_id: str):
    fpath = os.path.join(HISTORY_DIR, f"{chat_id}.json")
    if not os.path.exists(fpath):
        return JSONResponse({"messages": []}, status_code=404)
    with open(fpath, "r", encoding="utf-8") as f:
        data = json.load(f)
    return JSONResponse(data)


@app.post("/history/save")
async def history_save(request: Request):
    body = await request.json()
    chat_id = body.get("id")
    messages = body.get("messages", [])
    context_diary = body.get("context_diary")
    if not chat_id:
        return JSONResponse({"error": "Missing id"}, status_code=400)

    fpath = os.path.join(HISTORY_DIR, f"{chat_id}.json")
    # Preserve existing title and context_diary if file already exists
    title = ""
    existing_diary = ""
    if os.path.exists(fpath):
        try:
            with open(fpath, "r", encoding="utf-8") as f:
                existing = json.load(f)
            title = existing.get("title", "")
            existing_diary = existing.get("context_diary", "")
        except Exception:
            pass

    data = {
        "id": chat_id,
        "title": title,
        "messages": messages,
        "context_diary": context_diary if context_diary is not None else existing_diary,
        "updatedAt": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    with open(fpath, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)
    return JSONResponse({"ok": True})


@app.post("/history/rename")
async def history_rename(request: Request):
    body = await request.json()
    chat_id = body.get("id")
    new_title = body.get("title", "")
    if not chat_id:
        return JSONResponse({"error": "Missing id"}, status_code=400)

    fpath = os.path.join(HISTORY_DIR, f"{chat_id}.json")
    if not os.path.exists(fpath):
        return JSONResponse({"error": "Not found"}, status_code=404)

    with open(fpath, "r", encoding="utf-8") as f:
        data = json.load(f)
    data["title"] = new_title
    with open(fpath, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)
    return JSONResponse({"ok": True})


@app.post("/history/delete")
async def history_delete(request: Request):
    body = await request.json()
    chat_id = body.get("id")
    if not chat_id:
        return JSONResponse({"error": "Missing id"}, status_code=400)

    fpath = os.path.join(HISTORY_DIR, f"{chat_id}.json")
    if os.path.exists(fpath):
        os.remove(fpath)
    return JSONResponse({"ok": True})


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
import re

def clean_bot_text(text):
    """Strip internal tool commands from bot reply text."""
    t = re.sub(r'<FUNCTION_CALL>[\s\S]*?</FUNCTION_CALL>', '', text)
    t = re.sub(r'<CONTEXT>[\s\S]*?</CONTEXT>', '', t)
    t = re.sub(r'^read\([^)]*\)\s*$', '', t, flags=re.MULTILINE)
    return t.strip()


# ---------------------------------------------------------------------------
# SSE Chat endpoint
# ---------------------------------------------------------------------------
@app.post("/chat")
async def chat(request: Request):
    body = await request.json()
    messages = body.get("messages", [])
    chat_id = body.get("chat_id", "")

    # Strip frontend display markers from messages before sending to model
    clean_messages = []
    for msg in messages:
        if msg.get("role") == "assistant":
            text = msg["content"][0]["text"]
            text = re.sub(r'\{\{(?:TOOL|READ):[^}]+\}\}', '', text).strip()
            if not text:
                text = "(continued)"
            clean_messages.append({"role": "assistant", "content": [{"text": text}]})
        else:
            clean_messages.append(msg)

    async def event_stream():
        # Use DEALER to receive multiple stream chunks from the ROUTER
        sock = zmq_ctx.socket(zmq.DEALER)
        # Generate a unique identity for this specific request
        import uuid
        sock.setsockopt_string(zmq.IDENTITY, str(uuid.uuid4()))
        sock.connect("tcp://127.0.0.1:5557")
        try:
            # Send the conversation + chat_id to v-aws.py
            await sock.send_json({"messages": clean_messages, "chat_id": chat_id})

            # Continuously yield chunks to the frontend as v-aws sends them
            while True:
                # ROUTER/DEALER: receive the payload directly
                reply = await sock.recv_json()

                if reply.get("error"):
                    yield f"data: {json.dumps({'error': reply['error']})}\n\n"
                    break

                if reply.get("done"):
                    done_payload = {"done": True}
                    if "total_tokens" in reply:
                        done_payload["total_tokens"] = reply["total_tokens"]
                    yield f"data: {json.dumps(done_payload)}\n\n"
                    break

                # chain_step: finalize current bubble, next text starts a new one
                if reply.get("chain_step"):
                    yield f"data: {json.dumps({'chain_step': True})}\n\n"
                    continue

                # Stream the text chunk
                raw_text = reply.get("text", "")
                cleaned = clean_bot_text(raw_text)
                
                if cleaned:
                    words = cleaned.split(" ")
                    for i, word in enumerate(words):
                        chunk = word if i == 0 else " " + word
                        yield f"data: {json.dumps({'text': chunk})}\n\n"
                        await asyncio.sleep(0.02)

                # If a tool was triggered, inject an inline badge marker into the text stream
                if reply.get("tool_active"):
                    # Attempt to extract the specific tool name
                    extracted_tool = "function"  # default fallback
                    
                    # Check for read(x)
                    read_match = re.search(r'read\(([^)]+)\)', raw_text)
                    if read_match:
                        extracted_tool = read_match.group(1).strip()
                    else:
                        # Check for <FUNCTION_CALL> JSON
                        func_match = re.search(r'<FUNCTION_CALL>([\s\S]*?)</FUNCTION_CALL>', raw_text)
                        if func_match:
                            try:
                                func_json = json.loads(func_match.group(1).strip())
                                extracted_tool = func_json.get("function", "function")
                            except:
                                pass

                    # Inject the tool marker directly into the text stream
                    marker_type = "READ" if read_match else "TOOL"
                    yield f"data: {json.dumps({'text': f'{{{{{marker_type}:{extracted_tool}}}}}'})}\n\n"
                    yield f"data: {json.dumps({'processing': True})}\n\n"

        except Exception as e:
            yield f"data: {json.dumps({'error': str(e)})}\n\n"
        finally:
            sock.close()

    return StreamingResponse(event_stream(), media_type="text/event-stream")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    print("[API] Gateway starting on http://127.0.0.1:5000")
    uvicorn.run(app, host="127.0.0.1", port=5000, log_level="warning")
