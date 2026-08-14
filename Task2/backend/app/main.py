"""
FastAPI application — Voice-Enabled RAG Pipeline.

Endpoints:
  POST /api/query     — accepts audio blob, returns answer + citations + latency
  POST /api/query-text — accepts text query (for testing without mic)
  GET  /api/health    — health check
  GET  /api/stats     — running P50/P70/P100 latency stats
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI, File, UploadFile, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from app.config import settings
from app.models import PipelineResponse, LatencyStats
from app.pipeline import orchestrator, retrieval
from app.utils.latency import latency_tracker


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Load FAISS index + embedding model at startup."""
    print("Starting Voice RAG Pipeline...")
    print(f"   Language: {settings.primary_language}")
    print(f"   Model: {settings.generation_model}")
    print(f"   Threshold: {settings.similarity_threshold}")

    # Load FAISS index
    try:
        retrieval.init_retrieval(settings.index_dir)
        print("FAISS index loaded")
    except Exception as e:
        print(f"FAISS index not found ({e}). Run ingest.py first.")

    # Pre-load embedding model
    try:
        from app.pipeline.embeddings import get_model
        get_model()
        print("Embedding model loaded (or fallback applied)")
    except Exception as e:
        print(f"Embedding model failed to load: {e}")

    yield
    print("Shutting down...")


app = FastAPI(
    title="Voice RAG Pipeline — HH Goa 2026",
    description="Speak a Hindi question, get a grounded, cited answer.",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS — allow frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Endpoints ────────────────────────────────────────────────

@app.get("/api/health")
async def health():
    return {"status": "ok", "language": settings.primary_language}


@app.get("/api/stats", response_model=LatencyStats)
async def stats():
    """Live P50/P70/P100 latency readout."""
    return latency_tracker.stats()


@app.post("/api/query", response_model=PipelineResponse)
async def query_voice(audio: UploadFile = File(...)):
    """
    Accept audio blob (WAV/WebM) → run full pipeline → return answer.
    """
    try:
        audio_bytes = await audio.read()
        if not audio_bytes:
            raise HTTPException(status_code=400, detail="Empty audio file")

        result = await orchestrator.run_pipeline(audio_bytes)
        return result

    except HTTPException:
        raise
    except Exception as e:
        return PipelineResponse(
            transcript="",
            answer="",
            guardrail={
                "passed": False,
                "status": "blocked_offtopic",
                "reason": f"Pipeline error: {str(e)}. Please try again.",
            },
        )


class TextQuery(BaseModel):
    query: str


@app.post("/api/query-text", response_model=PipelineResponse)
async def query_text(body: TextQuery):
    """
    Accept text query → run pipeline (skip STT) → return answer.
    For testing and benchmarking without a microphone.
    """
    if not body.query.strip():
        raise HTTPException(status_code=400, detail="Empty query")

    try:
        result = await orchestrator.run_pipeline_text(body.query)
        return result
    except Exception as e:
        return PipelineResponse(
            transcript=body.query,
            answer="",
            guardrail={
                "passed": False,
                "status": "blocked_offtopic",
                "reason": f"Pipeline error: {str(e)}. Please try again.",
            },
        )
