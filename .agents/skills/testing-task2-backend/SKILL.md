---
name: testing-task2-backend
description: How to set up, run, and test the Task2 Voice RAG backend (FastAPI + FAISS + BM25) and frontend without Groq/Sarvam API keys
---

# Testing the Task2 Voice RAG backend

## Setup (CPU box, ~10 min)
- `cd Task2/backend && python3 -m venv venv && ./venv/bin/pip install -r requirements.txt` (installs torch CPU, faiss-cpu, sentence-transformers).
- `./venv/bin/python scripts/download_nltk.py` (chunking needs punkt/wordnet).
- Config is pydantic BaseSettings reading `Task2/backend/.env`. `SARVAM_API_KEY` and `GROQ_API_KEY` are required fields — set dummy values if you only test retrieval.

## Testing retrieval without a GROQ_API_KEY
- Set `SIMILARITY_THRESHOLD=1.1` in `.env`: the post-retrieval guardrail then always blocks BEFORE generation, and `/api/query-text` (and the frontend) still return the top retrieval score, retrieved chunks, and full latency breakdown (embedding_ms / retrieval_ms). This is the cleanest way to prove retrieval works with no LLM key.
- Full pipeline (generation, groundedness) needs a real `GROQ_API_KEY`; STT needs `SARVAM_API_KEY`.

## Building a test index quickly
- Defaults (`EMBEDDING_MODEL=intfloat/multilingual-e5-large`, `DATASET_SAMPLE_SIZE=3000`) are too heavy for a small CPU box. Use `EMBEDDING_MODEL=intfloat/multilingual-e5-small` and `DATASET_SAMPLE_SIZE=100` → ~8.7k chunks, ingest completes in ~4 min: `./venv/bin/python -m scripts.ingest`. Writes faiss.index / metadata.json / queries.json to `INDEX_DIR` (default `app/data`).
- 100 samples yields ~8736 vectors, conveniently ≥ 200*40, so the IVF branch (`FAISS_INDEX_TYPE=ivf`, default `FAISS_NLIST=200`) is reachable.
- To rebuild the index with different FAISS settings WITHOUT re-embedding: `faiss.read_index(...).reconstruct_n(0, n)` the vectors from the existing flat index, rebuild `Chunk(**m)` from metadata.json, and call `app.pipeline.indexer.build_index` into a new dir; then point the server at it with `INDEX_DIR=...`.

## Running
- Backend: `PYTHONUNBUFFERED=1 ./venv/bin/uvicorn app.main:app --port 8000` (unbuffered so the "Retrieval initialized: N vectors (bm25_hybrid=on/off)" startup line appears in logs). Startup takes ~20–30s (loads embedding model).
- Beware: `pkill -f uvicorn` from a `bash -c` one-shot kills the calling shell too (pattern matches its own cmdline); use plain `pkill uvicorn`.
- Frontend: `cd Task2/frontend && npm install && npm run dev` → :3000, vite proxies `/api` → :8000. Text queries via the input box hit `/api/query-text`; the decline card shows retrieval score/threshold and the latency breakdown grid shows Retrieve ms.
- Typing Devanagari via xdotool-style `type` fails (renders "?"); install `xclip`, put the Hindi query on the clipboard, and paste with ctrl+v.

## Devin Secrets Needed
- `GROQ_API_KEY` (generation + groundedness), `SARVAM_API_KEY` (STT) — only for full-pipeline tests; retrieval-only testing works with dummies.
