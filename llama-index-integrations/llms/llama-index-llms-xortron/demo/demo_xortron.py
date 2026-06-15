#!/usr/bin/env python3
"""
Self-contained demo for the Xortron LLM integration.

Starts a FastAPI mock server that implements the Xortron inference protocol,
then exercises every Xortron client method: complete, chat, stream_complete,
and stream_chat.

Usage:
    pip install llama-index-llms-xortron fastapi uvicorn
    python demo_xortron.py
"""

import asyncio
import json
import threading
import time
from typing import Any, Dict, List

import uvicorn
from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

# ---------------------------------------------------------------------------
# Mock Xortron inference server
# ---------------------------------------------------------------------------

app = FastAPI(title="Mock Xortron Server")

CANNED_RESPONSE = (
    "Paris is the capital of France. It is known as the City of Light "
    "and is famous for the Eiffel Tower, the Louvre, and its vibrant culture."
)


class CompletionRequest(BaseModel):
    model: str = "xortron-default"
    prompt: str = ""
    temperature: float = 0.7
    max_tokens: int = 256
    stream: bool = False


class ChatRequest(BaseModel):
    model: str = "xortron-default"
    messages: List[Dict[str, str]] = []
    temperature: float = 0.7
    max_tokens: int = 256
    stream: bool = False


def _stream_tokens(text: str):
    words = text.split(" ")
    for i, word in enumerate(words):
        token = word if i == 0 else " " + word
        yield f"data: {json.dumps({'text': token})}\n\n"
        time.sleep(0.05)
    yield "data: [DONE]\n\n"


async def _async_stream_tokens(text: str):
    words = text.split(" ")
    for i, word in enumerate(words):
        token = word if i == 0 else " " + word
        yield f"data: {json.dumps({'text': token})}\n\n"
        await asyncio.sleep(0.05)
    yield "data: [DONE]\n\n"


@app.post("/v1/completions")
async def completions(req: CompletionRequest):
    if req.stream:
        return StreamingResponse(
            _async_stream_tokens(CANNED_RESPONSE),
            media_type="text/event-stream",
        )
    return {"text": CANNED_RESPONSE, "model": req.model}


@app.post("/v1/chat")
async def chat(req: ChatRequest):
    user_msg = ""
    for m in req.messages:
        if m.get("role") == "user":
            user_msg = m.get("content", "")

    reply = f"You asked: '{user_msg}'. {CANNED_RESPONSE}"

    if req.stream:
        return StreamingResponse(
            _async_stream_tokens(reply),
            media_type="text/event-stream",
        )
    return {"message": {"role": "assistant", "content": reply}, "model": req.model}


@app.get("/health")
async def health():
    return {"status": "ok"}


# ---------------------------------------------------------------------------
# Demo client
# ---------------------------------------------------------------------------


def run_demo():
    from llama_index.llms.xortron import Xortron

    llm = Xortron(model="xortron-7b", base_url="http://localhost:9119")

    print("=" * 60)
    print("XORTRON LLM DEMO")
    print("=" * 60)

    # 1. complete()
    print("\n--- complete() ---")
    resp = llm.complete("What is the capital of France?")
    print(f"Response: {resp.text}")

    # 2. chat()
    print("\n--- chat() ---")
    from llama_index.core.base.llms.types import ChatMessage, MessageRole

    messages = [
        ChatMessage(role=MessageRole.SYSTEM, content="You are a helpful assistant."),
        ChatMessage(role=MessageRole.USER, content="What is the capital of France?"),
    ]
    chat_resp = llm.chat(messages)
    print(f"Response: {chat_resp.message.blocks[0].text}")

    # 3. stream_complete()
    print("\n--- stream_complete() ---")
    print("Streaming: ", end="", flush=True)
    for chunk in llm.stream_complete("Tell me about France."):
        if chunk.delta:
            print(chunk.delta, end="", flush=True)
    print()

    # 4. stream_chat()
    print("\n--- stream_chat() ---")
    print("Streaming: ", end="", flush=True)
    for chunk in llm.stream_chat(messages):
        if chunk.delta:
            print(chunk.delta, end="", flush=True)
    print()

    print("\n" + "=" * 60)
    print("ALL DEMOS PASSED")
    print("=" * 60)


def main():
    server = uvicorn.Server(
        uvicorn.Config(app, host="0.0.0.0", port=9119, log_level="warning")
    )
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    time.sleep(1.5)

    try:
        run_demo()
    finally:
        server.should_exit = True
        thread.join(timeout=3)


if __name__ == "__main__":
    main()
