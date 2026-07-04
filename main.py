"""
Qwen3 Chatbot — FastAPI backend.

Two backends, chosen with the CHAT_BACKEND env var:

  CHAT_BACKEND=local   (default)  -> loads a Qwen model locally with transformers
  CHAT_BACKEND=api                -> forwards to any OpenAI-compatible endpoint
                                     (DashScope, Ollama, vLLM, OpenRouter, etc.)

Environment variables
---------------------
  CHAT_BACKEND   local | api                (default: local)
  MODEL_NAME     HF repo id or API model    (default: Qwen/Qwen3-0.6B)
  ENABLE_THINKING  1 | 0                     (default: 0  -> direct answers)

  # only used when CHAT_BACKEND=api
  OPENAI_BASE_URL  e.g. https://dashscope-intl.aliyuncs.com/compatible-mode/v1
  OPENAI_API_KEY   your key
"""

import os
import re
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

# --------------------------------------------------------------------------- #
# Config
# --------------------------------------------------------------------------- #
CHAT_BACKEND = os.getenv("CHAT_BACKEND", "local").lower()
MODEL_NAME = os.getenv("MODEL_NAME", "Qwen/Qwen3-0.6B")
ENABLE_THINKING = os.getenv("ENABLE_THINKING", "0") == "1"
FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"

# Filled in at startup when using the local backend.
_model = None
_tokenizer = None


# --------------------------------------------------------------------------- #
# Request / response schema
# --------------------------------------------------------------------------- #
class Message(BaseModel):
    role: str = Field(..., pattern="^(system|user|assistant)$")
    content: str


class ChatRequest(BaseModel):
    messages: list[Message]
    max_tokens: int = 512
    temperature: float = 0.7


class ChatResponse(BaseModel):
    reply: str


# --------------------------------------------------------------------------- #
# Local (transformers) backend
# --------------------------------------------------------------------------- #
def load_local_model() -> None:
    """Load the Qwen model + tokenizer once, at startup."""
    global _model, _tokenizer
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer

    print(f"[startup] loading '{MODEL_NAME}' with transformers ...")
    _tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)
    _model = AutoModelForCausalLM.from_pretrained(
        MODEL_NAME,
        torch_dtype="auto",
        device_map="auto" if torch.cuda.is_available() else None,
    )
    print("[startup] model ready.")


def _strip_thinking(text: str) -> str:
    """Remove Qwen3 <think>...</think> blocks so the UI shows the final answer."""
    return re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()


def generate_local(req: ChatRequest) -> str:
    import torch

    messages = [m.model_dump() for m in req.messages]
    prompt = _tokenizer.apply_chat_template(
        messages,
        tokenize=False,
        add_generation_prompt=True,
        enable_thinking=ENABLE_THINKING,
    )
    inputs = _tokenizer(prompt, return_tensors="pt").to(_model.device)

    with torch.no_grad():
        generated = _model.generate(
            **inputs,
            max_new_tokens=req.max_tokens,
            temperature=req.temperature,
            top_p=0.9,
            do_sample=req.temperature > 0,
            pad_token_id=_tokenizer.eos_token_id,
        )

    # Keep only the newly generated tokens.
    new_tokens = generated[0][inputs["input_ids"].shape[1]:]
    text = _tokenizer.decode(new_tokens, skip_special_tokens=True)
    return _strip_thinking(text)


# --------------------------------------------------------------------------- #
# API (OpenAI-compatible) backend
# --------------------------------------------------------------------------- #
def generate_api(req: ChatRequest) -> str:
    import httpx

    base_url = os.getenv("OPENAI_BASE_URL")
    api_key = os.getenv("OPENAI_API_KEY")
    if not base_url or not api_key:
        raise HTTPException(
            500, "CHAT_BACKEND=api requires OPENAI_BASE_URL and OPENAI_API_KEY."
        )

    payload = {
        "model": MODEL_NAME,
        "messages": [m.model_dump() for m in req.messages],
        "max_tokens": req.max_tokens,
        "temperature": req.temperature,
    }
    resp = httpx.post(
        f"{base_url.rstrip('/')}/chat/completions",
        headers={"Authorization": f"Bearer {api_key}"},
        json=payload,
        timeout=120,
    )
    resp.raise_for_status()
    return _strip_thinking(resp.json()["choices"][0]["message"]["content"])


# --------------------------------------------------------------------------- #
# App lifecycle
# --------------------------------------------------------------------------- #
@asynccontextmanager
async def lifespan(app: FastAPI):
    if CHAT_BACKEND == "local":
        load_local_model()
    yield


app = FastAPI(title="Qwen3 Chatbot", lifespan=lifespan)

# Allow the frontend to call the API from anywhere (loosen for production).
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok", "backend": CHAT_BACKEND, "model": MODEL_NAME}


@app.post("/api/chat", response_model=ChatResponse)
def chat(req: ChatRequest) -> ChatResponse:
    if not req.messages:
        raise HTTPException(400, "messages must not be empty.")
    try:
        reply = generate_local(req) if CHAT_BACKEND == "local" else generate_api(req)
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(500, f"generation failed: {exc}") from exc
    return ChatResponse(reply=reply or "…")


# Serve the frontend (index.html, style.css, script.js) at the root.
# Mounted last so /api/* routes take priority.
if FRONTEND_DIR.exists():
    app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")
