# Qwen3 Chatbot

A minimal chatbot with a **FastAPI** backend and a lightweight **HTML/CSS/JS** frontend.
Runs an open-weights **Qwen** model locally with `transformers`, or forwards to any
OpenAI-compatible API (DashScope, Ollama, vLLM, OpenRouter…).

```
qwen-chatbot/
├── app/
│   └── main.py            # FastAPI backend (also serves the frontend)
├── frontend/
│   ├── index.html
│   ├── style.css
│   └── script.js
├── requirements.txt
├── Dockerfile
├── .github/workflows/ci.yml
└── README.md
```

---

## 1. Run locally

```bash
git clone https://github.com/<you>/qwen-chatbot.git
cd qwen-chatbot

python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt

uvicorn app.main:app --reload
```

Open **http://localhost:8000**. The first run downloads the model
(`Qwen/Qwen3-0.6B`, ~1.5 GB) — later runs are instant.

### Two ways to run

| Mode | Env vars | Notes |
|------|----------|-------|
| **Local model** (default) | `CHAT_BACKEND=local` `MODEL_NAME=Qwen/Qwen3-0.6B` | No API key. Needs ~2 GB RAM for the 0.6B model. Swap `MODEL_NAME` for `Qwen/Qwen3-1.7B`, `Qwen/Qwen3-4B`, etc. if you have the hardware. |
| **API** | `CHAT_BACKEND=api` `OPENAI_BASE_URL=…` `OPENAI_API_KEY=…` `MODEL_NAME=qwen-plus` | No local weights, tiny footprint. Great for free hosting. |

Example, using Alibaba's DashScope (OpenAI-compatible):

```bash
export CHAT_BACKEND=api
export OPENAI_BASE_URL=https://dashscope-intl.aliyuncs.com/compatible-mode/v1
export OPENAI_API_KEY=sk-...
export MODEL_NAME=qwen-plus
uvicorn app.main:app --reload
```

Other config: `ENABLE_THINKING=1` turns on Qwen3's reasoning mode (slower, more thorough).

---

## 2. Deploy

> **Important:** GitHub *stores* your code — it does **not** run a Python server.
> GitHub Pages can only host the static `frontend/` (no backend). To run FastAPI,
> connect your GitHub repo to a host that executes code. All options below deploy
> straight from the repo you push in Step 0.

### Step 0 — Push to GitHub (do this first)

```bash
git init
git add .
git commit -m "Qwen3 chatbot"
git branch -M main
git remote add origin https://github.com/<you>/qwen-chatbot.git
git push -u origin main
```

### Option A — Hugging Face Spaces  *(best for the local Qwen model)*

Spaces gives you more RAM than most free tiers, so the model actually fits.

1. Create a new Space → SDK: **Docker**.
2. Link it to your GitHub repo (Space settings → *Link to a GitHub repository*),
   **or** push the same files to the Space's git remote.
3. It builds from the `Dockerfile` automatically and serves on port 7860 —
   the `$PORT` in the Dockerfile handles this. Done.

### Option B — Render  *(best for the API backend)*

The free tier is memory-limited, so use `CHAT_BACKEND=api` here (skip the local model).

1. [render.com](https://render.com) → **New → Web Service** → connect your GitHub repo.
2. Runtime: **Docker** (it detects the `Dockerfile`).
3. Add environment variables: `CHAT_BACKEND=api`, `OPENAI_BASE_URL`, `OPENAI_API_KEY`, `MODEL_NAME`.
4. Deploy. Render auto-redeploys on every push to `main`.

Railway, Fly.io, and Google Cloud Run work the same way — point them at the repo,
they read the `Dockerfile`.

### Option C — GitHub Pages (frontend only)

Pages can host the UI but **not** the backend, so you still need the backend running
somewhere from Option A or B.

1. In `frontend/script.js`, set `API_BASE` to your backend URL
   (e.g. `"https://your-app.onrender.com"`).
2. Repo → **Settings → Pages** → deploy from branch `main`, folder `/frontend`
   (move the frontend to `/docs` if Pages requires it).
3. Your chat UI is live on `https://<you>.github.io/qwen-chatbot/`.

---

## Notes

- **CORS** is wide open (`allow_origins=["*"]`) for easy setup. Restrict it to your
  frontend's domain before going to production.
- The frontend sends the **full conversation history** each turn, so the model
  keeps context. Long chats grow the request — trim old turns if needed.
- Responses are **not streamed** (kept simple). For token-by-token streaming, swap
  `generate()` for a `TextIteratorStreamer` and return a `StreamingResponse`.
