# Voice-Enabled RAG Pipeline — HH Goa 2026 · Task #2

> **#RAGInGoa** — Speak a question in Hindi, get a grounded, cited answer from MSMARCO-XI.

## 🎯 What it does

1. **Voice Input** → Sarvam AI Saaras v3 transcribes spoken Hindi
2. **Multi-Strategy Chunking** → 4 strategies (fixed-size, semantic, sentence-window, metadata-aware) feed one combined FAISS index
3. **Hybrid Retrieval** → FAISS vector search + BM25 keyword matching via reciprocal rank fusion
4. **Grounded Generation** → Groq (Llama 3.1 70B) generates answers citing specific passage IDs
5. **Three-Layer Guardrails** → Pre-retrieval filter, confidence threshold, post-generation groundedness check
6. **Latency Benchmark** → P50/P70/P100 measured across real queries, displayed live in the UI

## 🏗️ Architecture

```
Voice → Sarvam STT → Guardrail (pre) → Embed query → FAISS retrieval
  → Rerank across strategies → Guardrail (post-retrieval) → Groq LLM
  → Guardrail (groundedness) → Answer + Citations
```

**Offline pipeline**: MSMARCO-XI Hindi subset → Clean → 4 chunking strategies → BGE-M3/multilingual-e5 embeddings → FAISS index

## 🚀 Quick Start

### Prerequisites
- Python 3.10+
- Node.js 18+
- Sarvam AI API key
- Groq API key

### Backend Setup

```bash
cd Task2/backend

# Create virtual environment
python -m venv venv
venv\Scripts\activate  # Windows
# source venv/bin/activate  # macOS/Linux

# Install dependencies
pip install -r requirements.txt

# Configure API keys
cp .env.example .env
# Edit .env with your API keys

# Run offline ingestion (builds FAISS index — run once)
python -m scripts.ingest

# Start the API server
uvicorn app.main:app --reload --port 8000
```

### Frontend Setup

```bash
cd Task2/frontend
npm install
npm run dev
```

Open http://localhost:3000 — speak a Hindi question or type one.

### Run Latency Benchmark

```bash
cd Task2/backend
python -m scripts.benchmark
```

## 📊 Tech Stack

| Layer | Technology |
|---|---|
| STT | Sarvam AI (Saaras v3) |
| Embeddings | multilingual-e5-large (local) |
| Vector Store | FAISS (in-process) |
| Generation | Groq (Llama 3.1 70B) |
| Backend | FastAPI + Pydantic + tenacity |
| Frontend | Vite + vanilla JS |
| Dataset | MSMARCO-XI Hindi subset |

## 🛡️ Guardrails

1. **Pre-retrieval**: Regex/keyword filter for unsafe/off-topic queries → early reject
2. **Post-retrieval**: Similarity threshold (configurable, default 0.55) → refuse if top score too low
3. **Post-generation**: LLM groundedness check → refuse if answer not supported by passages

The UI explicitly shows guardrail-declined states with scores and thresholds — not just happy-path answers.

## ⚡ Latency

Target: **retrieval + generation ≤ 200ms** (post-STT). STT latency reported separately.

- FAISS in-process search: sub-millisecond
- Groq LLM inference: 500-2000+ tok/s
- Benchmark harness reports P50/P70/P100 across real queries

## 📁 Project Structure

```
Task2/
├── backend/
│   ├── app/
│   │   ├── main.py              # FastAPI endpoints
│   │   ├── config.py            # Pydantic settings
│   │   ├── models.py            # Typed schemas for every stage
│   │   ├── pipeline/
│   │   │   ├── stt.py           # Sarvam STT
│   │   │   ├── chunking.py      # 4 chunking strategies
│   │   │   ├── embeddings.py    # multilingual-e5-large
│   │   │   ├── indexer.py       # FAISS index builder
│   │   │   ├── retrieval.py     # FAISS + BM25 hybrid
│   │   │   ├── reranker.py      # Cross-strategy merge
│   │   │   ├── generator.py     # Groq LLM
│   │   │   ├── guardrails.py    # 3-layer guardrails
│   │   │   └── orchestrator.py  # Pipeline controller
│   │   └── utils/
│   │       ├── logger.py        # Structured JSON logging
│   │       └── latency.py       # Rolling P50/P70/P100 tracker
│   ├── scripts/
│   │   ├── ingest.py            # Offline indexing pipeline
│   │   └── benchmark.py         # Latency benchmark harness
│   └── requirements.txt
├── frontend/
│   ├── index.html
│   ├── src/
│   │   ├── main.js              # Mic capture + state machine
│   │   └── style.css            # Task 1 visual language
│   ├── package.json
│   └── vite.config.js
└── README.md
```

## 👥 Team

HH Goa 2026 — Task 2

---

*Built with 🎙️ for #RAGInGoa*
