"""
FAISS retrieval + optional BM25 hybrid.
Loads the pre-built index at startup and searches at query time.
"""

from __future__ import annotations

import numpy as np
import faiss
from rank_bm25 import BM25Okapi

from app.config import settings
from app.models import Chunk, ChunkStrategy, RetrievalResult
from app.pipeline.indexer import load_index
from app.utils.latency import timed_ms

# ── Module-level state (loaded once at startup) ──────────────

_faiss_index: faiss.Index | None = None
_metadata: list[dict] = []
_bm25: BM25Okapi | None = None
_chunk_texts: list[str] = []


def init_retrieval(index_dir: str | None = None):
    """Load FAISS index + metadata into memory. Call once at startup."""
    global _faiss_index, _metadata, _bm25, _chunk_texts

    index_dir = index_dir or settings.index_dir
    _faiss_index, _metadata = load_index(index_dir)

    # Build BM25 index for hybrid search
    _chunk_texts = [m.get("text", "") for m in _metadata]
    tokenized = [t.split() for t in _chunk_texts]
    _bm25 = BM25Okapi(tokenized)

    print(f"Retrieval initialized: {_faiss_index.ntotal} vectors loaded")


def search_faiss(
    query_embedding: np.ndarray,
    top_k: int | None = None,
) -> list[RetrievalResult]:
    """Vector similarity search using FAISS."""
    if _faiss_index is None:
        raise RuntimeError("Retrieval not initialized. Call init_retrieval() first.")

    top_k = top_k or settings.top_k
    query_vec = query_embedding.reshape(1, -1).astype(np.float32)
    
    if np.all(query_vec == 0):
        # Fallback was triggered, skip FAISS vector search entirely
        return []

    scores, indices = _faiss_index.search(query_vec, top_k)

    results = []
    for score, idx in zip(scores[0], indices[0]):
        if idx < 0:
            continue
        meta = _metadata[idx]
        results.append(RetrievalResult(
            chunk_id=meta.get("chunk_id", ""),
            chunk_text=meta.get("text", ""),
            score=float(score),
            strategy=ChunkStrategy(meta.get("strategy", "fixed_size")),
            passage_id=meta.get("passage_id", ""),
            window_context=meta.get("window_context", ""),
        ))

    return results


def search_bm25(query: str, top_k: int | None = None) -> list[RetrievalResult]:
    """BM25 keyword search for exact entity/number matches."""
    if _bm25 is None:
        return []

    top_k = top_k or settings.top_k
    tokenized_query = query.split()
    scores = _bm25.get_scores(tokenized_query)

    # Get top-k indices
    top_indices = np.argsort(scores)[::-1][:top_k]

    results = []
    for idx in top_indices:
        if scores[idx] <= 0:
            continue
        meta = _metadata[idx]
        results.append(RetrievalResult(
            chunk_id=meta.get("chunk_id", ""),
            chunk_text=meta.get("text", ""),
            score=float(scores[idx]),
            strategy=ChunkStrategy(meta.get("strategy", "fixed_size")),
            passage_id=meta.get("passage_id", ""),
            window_context=meta.get("window_context", ""),
        ))

    return results


def hybrid_search(
    query: str,
    query_embedding: np.ndarray,
    top_k: int | None = None,
    vector_weight: float = 0.7,
) -> list[RetrievalResult]:
    """
    Reciprocal rank fusion of FAISS vector + BM25 keyword results.
    """
    top_k = top_k or settings.top_k
    k_rrf = 60  # RRF constant

    with timed_ms() as timing:
        vector_results = search_faiss(query_embedding, top_k=top_k * 2)
        bm25_results = search_bm25(query, top_k=top_k * 2)

    # Build RRF scores
    rrf_scores: dict[str, float] = {}
    chunk_map: dict[str, RetrievalResult] = {}

    for rank, r in enumerate(vector_results):
        rrf_scores[r.chunk_id] = rrf_scores.get(r.chunk_id, 0) + vector_weight / (k_rrf + rank + 1)
        chunk_map[r.chunk_id] = r

    for rank, r in enumerate(bm25_results):
        rrf_scores[r.chunk_id] = rrf_scores.get(r.chunk_id, 0) + (1 - vector_weight) / (k_rrf + rank + 1)
        if r.chunk_id not in chunk_map:
            chunk_map[r.chunk_id] = r

    # Sort by RRF score, take top_k
    sorted_ids = sorted(rrf_scores, key=lambda x: rrf_scores[x], reverse=True)[:top_k]

    results = []
    for cid in sorted_ids:
        r = chunk_map[cid]
        results.append(RetrievalResult(
            chunk_id=r.chunk_id,
            chunk_text=r.chunk_text,
            score=r.score,  # Keep original FAISS or BM25 score for guardrails
            strategy=r.strategy,
            passage_id=r.passage_id,
            window_context=r.window_context,
        ))

    return results
