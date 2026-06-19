from __future__ import annotations

import json
import os
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

# ---------------------------------------------------------------------------
# LLM selection — reads env vars at startup
# OLLAMA_CLOUD_API_KEY  → Ollama Cloud (gemma4:31b default)
# (unset)               → local Ollama (gemma4:12b default)
# OLLAMA_MODEL          → override model name
# OLLAMA_BASE_URL       → override endpoint
# ---------------------------------------------------------------------------
CLOUD_API_KEY = os.environ.get("OLLAMA_CLOUD_API_KEY", "")
BASE_URL = os.environ.get("OLLAMA_BASE_URL", "")
_default_model = "gemma4:31b" if CLOUD_API_KEY else "gemma4:12b"
MODEL = os.environ.get("OLLAMA_MODEL", _default_model)

if CLOUD_API_KEY:
    from llama_index.llms.openai_like import OpenAILike
    llm = OpenAILike(
        model=MODEL,
        api_base=BASE_URL or "https://ollama.com/v1",
        api_key=CLOUD_API_KEY,
        is_chat_model=True,
        context_window=128_000,
        timeout=180.0,
    )
    print(f"[server] Ollama CLOUD — model: {MODEL}")
else:
    from llama_index.llms.ollama import Ollama
    llm = Ollama(
        model=MODEL,
        base_url=BASE_URL or "http://localhost:11434",
        request_timeout=180.0,
    )
    print(f"[server] LOCAL Ollama — model: {MODEL}")

from llama_index.core.llms import ChatMessage  # noqa: E402

# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------
app = FastAPI(title="Gemma 4 Chat API")

ALLOWED_ORIGINS = os.environ.get("ALLOWED_ORIGINS", "*").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_methods=["POST", "GET", "OPTIONS"],
    allow_headers=["*"],
)


class ChatRequest(BaseModel):
    messages: list[dict]


@app.get("/health")
async def health() -> dict:
    return {"status": "ok", "model": MODEL, "mode": "cloud" if CLOUD_API_KEY else "local"}


@app.post("/chat")
async def chat(req: ChatRequest) -> dict:
    messages = [ChatMessage(role=m["role"], content=m["content"]) for m in req.messages]
    response = await llm.achat(messages)
    return {"content": str(response.message.content)}


async def _stream_tokens(messages: list[ChatMessage]) -> AsyncGenerator[str, None]:
    async for chunk in await llm.astream_chat(messages):
        if chunk.delta:
            yield f"data: {json.dumps({'delta': chunk.delta})}\n\n"
    yield "data: [DONE]\n\n"


@app.post("/stream")
async def stream_chat(req: ChatRequest) -> StreamingResponse:
    messages = [ChatMessage(role=m["role"], content=m["content"]) for m in req.messages]
    return StreamingResponse(
        _stream_tokens(messages),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
