"""
Pydantic schemas for every pipeline stage's input/output.
Structured I/O as required by PRD §4.6 — no raw dicts flying between stages.
"""

from __future__ import annotations
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field


# ── Enums ─────────────────────────────────────────────────────

class ChunkStrategy(str, Enum):
    FIXED_SIZE = "fixed_size"
    SEMANTIC = "semantic"
    SENTENCE_WINDOW = "sentence_window"
    METADATA_AWARE = "metadata_aware"


class GuardrailStatus(str, Enum):
    PASSED = "passed"
    BLOCKED_OFFTOPIC = "blocked_offtopic"
    BLOCKED_UNSAFE = "blocked_unsafe"
    BLOCKED_LOW_CONFIDENCE = "blocked_low_confidence"
    BLOCKED_UNGROUNDED = "blocked_ungrounded"


# ── STT ───────────────────────────────────────────────────────

class STTResponse(BaseModel):
    transcript: str
    language: str = "hi"
    latency_ms: float = 0.0


# ── Chunks ────────────────────────────────────────────────────

class Chunk(BaseModel):
    chunk_id: str
    text: str
    strategy: ChunkStrategy
    passage_id: str = ""
    query_id: str = ""
    query_type: str = ""
    language: str = "hi"
    language_name: str | None = None
    source_lang: str | None = None
    target_lang: str | None = None
    english_text: str | None = None
    passage_index: int | None = None
    is_selected: int | None = None
    # For sentence-window: neighboring sentences stored for retrieval-time expansion
    window_context: str = ""


# ── Retrieval ─────────────────────────────────────────────────

class RetrievalResult(BaseModel):
    chunk_id: str
    chunk_text: str
    score: float
    strategy: ChunkStrategy
    passage_id: str = ""
    window_context: str = ""


# ── Generation ────────────────────────────────────────────────

class Citation(BaseModel):
    passage_id: str
    chunk_text: str = ""


class GenerationResponse(BaseModel):
    answer: str
    citations: list[Citation] = Field(default_factory=list)
    latency_ms: float = 0.0


# ── Guardrails ────────────────────────────────────────────────

class GuardrailDecision(BaseModel):
    passed: bool = True
    status: GuardrailStatus = GuardrailStatus.PASSED
    reason: str = ""
    score: float | None = None
    threshold: float | None = None


# ── Latency breakdown ────────────────────────────────────────

class LatencyBreakdown(BaseModel):
    stt_ms: float = 0.0
    guardrail_pre_ms: float = 0.0
    route_ms: float = 0.0
    web_search_ms: float = 0.0
    embedding_ms: float = 0.0
    retrieval_ms: float = 0.0
    rerank_ms: float = 0.0
    guardrail_post_retrieval_ms: float = 0.0
    generation_ms: float = 0.0
    guardrail_post_gen_ms: float = 0.0
    total_ms: float = 0.0
    # retrieval+generation only (the 200ms budget)
    rag_ms: float = 0.0


class StrategyStats(BaseModel):
    strategy: ChunkStrategy
    avg_score: float = 0.0
    win_count: int = 0


# ── Pipeline response ────────────────────────────────────────

class PipelineResponse(BaseModel):
    transcript: str = ""
    language_name: str = "Hindi"
    route: str = "RAG"
    answer: str = ""
    citations: list[Citation] = Field(default_factory=list)
    guardrail: GuardrailDecision = Field(default_factory=GuardrailDecision)
    latency: LatencyBreakdown = Field(default_factory=LatencyBreakdown)
    strategy_stats: list[StrategyStats] = Field(default_factory=list)
    retrieved_chunks: list[RetrievalResult] = Field(default_factory=list)
    web_results: list[dict] = Field(default_factory=list)


# ── Latency stats (live readout) ─────────────────────────────

class LatencyStats(BaseModel):
    p50_ms: float = 0.0
    p70_ms: float = 0.0
    p100_ms: float = 0.0
    query_count: int = 0
