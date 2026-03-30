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
_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
MODELS_PATH = os.path.join(_SCRIPT_DIR, "models-list.json")
HISTORY_DIR = os.path.join(os.path.dirname(_SCRIPT_DIR), "history")


def _load_model_catalog():
    fallback_id = "moonshotai.kimi-k2.5"
    fallback = [{"id": fallback_id, "label": "Kimi K2.5"}]
    try:
        with open(MODELS_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict) and "models" in data:
            raw = data["models"]
        elif isinstance(data, list):
            raw = data
        else:
            return fallback, fallback_id
        catalog = []
        for m in raw:
            if isinstance(m, str):
                catalog.append({"id": m, "label": m})
            elif isinstance(m, dict) and m.get("id"):
                catalog.append({"id": m["id"], "label": m.get("label") or m["id"]})
        if catalog:
            return catalog, catalog[0]["id"]
    except Exception:
        pass
    return fallback, fallback_id


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
    catalog, default_id = _load_model_catalog()
    label = next((m["label"] for m in catalog if m["id"] == default_id), default_id)
    return {"name": label, "id": default_id}


@app.get("/models")
async def get_models():
    catalog, default_id = _load_model_catalog()
    return {"models": catalog, "default_id": default_id}

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
                "context_diary": data.get("context_diary", ""),
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
# AWS Credentials endpoints
# ---------------------------------------------------------------------------
SCRIPTS_DIR = _SCRIPT_DIR
CREDS_PATH = os.path.join(SCRIPTS_DIR, "aws_credentials.json")

@app.get("/credentials/status")
async def credentials_status():
    if not os.path.exists(CREDS_PATH):
        return JSONResponse({"configured": False})
    try:
        with open(CREDS_PATH, "r", encoding="utf-8") as f:
            creds = json.load(f)
        has_keys = bool(creds.get("AWS_ACCESS_KEY_ID")) and bool(creds.get("AWS_SECRET_ACCESS_KEY"))
        return JSONResponse({"configured": has_keys})
    except Exception:
        return JSONResponse({"configured": False})


@app.post("/credentials/save")
async def credentials_save(request: Request):
    body = await request.json()
    access_key = (body.get("aws_access_key_id") or "").strip()
    secret_key = (body.get("aws_secret_access_key") or "").strip()

    if not access_key or not secret_key:
        return JSONResponse({"error": "Both keys are required"}, status_code=400)

    creds = {
        "AWS_ACCESS_KEY_ID": access_key,
        "AWS_SECRET_ACCESS_KEY": secret_key,
    }
    try:
        with open(CREDS_PATH, "w", encoding="utf-8") as f:
            json.dump(creds, f, indent=4)
        return JSONResponse({"ok": True})
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
import re

def clean_bot_text(text):
    """Strip internal tool commands from bot reply text."""
    t = re.sub(r'<FUNCTION_CALL>[\s\S]*?</FUNCTION_CALL>', '', text)
    t = re.sub(r'<CONTEXT>[\s\S]*?</CONTEXT>', '', t, flags=re.IGNORECASE)
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
    catalog, default_id = _load_model_catalog()
    allowed_ids = {m["id"] for m in catalog}
    model_id = body.get("model_id") or default_id
    if model_id not in allowed_ids:
        model_id = default_id

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
            await sock.send_json(
                {"messages": clean_messages, "chat_id": chat_id, "model_id": model_id}
            )

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
                    
                    # Last read(x) matches reader worker (prose may mention another read first)
                    read_matches = list(re.finditer(r"read\(([^)]+)\)", raw_text))
                    read_match = read_matches[-1] if read_matches else None
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
