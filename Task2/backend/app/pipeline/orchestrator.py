"""
End-to-end pipeline orchestrator.
Wires: audio → STT → guardrail_pre → embed → retrieve → rerank →
       guardrail_post_retrieval → generate → guardrail_post_gen → response
Instruments every stage with perf_counter for the latency breakdown.
"""

from __future__ import annotations

import time
import uuid

from app.config import settings
from app.models import (
    PipelineResponse,
    LatencyBreakdown,
    GuardrailDecision,
    GuardrailStatus,
)
from app.pipeline import stt, retrieval, generator, guardrails, reranker, embeddings
from app.utils.latency import latency_tracker
from app.utils.logger import log_query


async def run_pipeline(audio_bytes: bytes) -> PipelineResponse:
    """
    Full pipeline: voice → answer (or refusal).
    Returns a structured PipelineResponse with latency breakdown.
    """
    query_id = uuid.uuid4().hex[:8]
    latency = LatencyBreakdown()
    response = PipelineResponse()

    # ── Step 1: Speech-to-text ────────────────────────────────
    try:
        t0 = time.perf_counter()
        stt_result = await stt.transcribe(audio_bytes)
        latency.stt_ms = round((time.perf_counter() - t0) * 1000, 2)
        response.transcript = stt_result.transcript
    except Exception as e:
        response.guardrail = GuardrailDecision(
            passed=False,
            status=GuardrailStatus.BLOCKED_OFFTOPIC,
            reason=f"Speech-to-text failed: {str(e)}. Please try again.",
        )
        response.latency = latency
        return response

    transcript = stt_result.transcript
    if not transcript.strip():
        response.guardrail = GuardrailDecision(
            passed=False,
            status=GuardrailStatus.BLOCKED_OFFTOPIC,
            reason="Could not detect speech. Please speak clearly and try again.",
        )
        response.latency = latency
        return response

    # ── Step 2: Pre-retrieval guardrail ───────────────────────
    t0 = time.perf_counter()
    pre_check = guardrails.check_pre_retrieval(transcript)
    latency.guardrail_pre_ms = round((time.perf_counter() - t0) * 1000, 2)

    if not pre_check.passed:
        response.guardrail = pre_check
        response.latency = latency
        return response

    # ── RAG timing starts here (the 200ms budget) ────────────
    rag_start = time.perf_counter()

    # ── Step 3: Embed query ───────────────────────────────────
    t0 = time.perf_counter()
    query_embedding = embeddings.embed_query(transcript)
    latency.embedding_ms = round((time.perf_counter() - t0) * 1000, 2)

    # ── Step 4: Retrieve ──────────────────────────────────────
    t0 = time.perf_counter()
    raw_results = retrieval.hybrid_search(
        query=transcript,
        query_embedding=query_embedding,
        top_k=settings.top_k * 2,  # Fetch more, reranker will trim
    )
    latency.retrieval_ms = round((time.perf_counter() - t0) * 1000, 2)

    # ── Step 5: Rerank ────────────────────────────────────────
    t0 = time.perf_counter()
    ranked_results, strategy_stats, winning_strategy = reranker.rerank_and_merge(
        raw_results, top_k=settings.top_k
    )
    latency.rerank_ms = round((time.perf_counter() - t0) * 1000, 2)
    response.strategy_stats = strategy_stats
    response.retrieved_chunks = ranked_results

    # ── Step 6: Post-retrieval guardrail ──────────────────────
    t0 = time.perf_counter()
    post_ret_check = guardrails.check_post_retrieval(ranked_results)
    latency.guardrail_post_retrieval_ms = round((time.perf_counter() - t0) * 1000, 2)

    if not post_ret_check.passed:
        response.guardrail = post_ret_check
        latency.rag_ms = round((time.perf_counter() - rag_start) * 1000, 2)
        response.latency = latency
        _log(query_id, transcript, ranked_results, winning_strategy, post_ret_check, latency)
        return response

    # ── Step 7: Generate answer ───────────────────────────────
    try:
        t0 = time.perf_counter()
        gen_result = await generator.generate_answer(transcript, ranked_results)
        latency.generation_ms = round((time.perf_counter() - t0) * 1000, 2)
        response.answer = gen_result.answer
        response.citations = gen_result.citations
    except Exception as e:
        response.guardrail = GuardrailDecision(
            passed=False,
            status=GuardrailStatus.BLOCKED_OFFTOPIC,
            reason=f"Generation failed: {str(e)}. Please try again.",
        )
        latency.rag_ms = round((time.perf_counter() - rag_start) * 1000, 2)
        response.latency = latency
        return response

    # ── Step 8: Post-generation groundedness check ────────────
    t0 = time.perf_counter()
    ground_check = await guardrails.check_groundedness(gen_result.answer, ranked_results)
    latency.guardrail_post_gen_ms = round((time.perf_counter() - t0) * 1000, 2)

    if not ground_check.passed:
        response.answer = ""
        response.citations = []
        response.guardrail = ground_check
        latency.rag_ms = round((time.perf_counter() - rag_start) * 1000, 2)
        response.latency = latency
        _log(query_id, transcript, ranked_results, winning_strategy, ground_check, latency)
        return response

    # ── All checks passed ─────────────────────────────────────
    latency.rag_ms = round((time.perf_counter() - rag_start) * 1000, 2)
    latency.total_ms = round(latency.stt_ms + latency.rag_ms + latency.guardrail_pre_ms, 2)
    response.guardrail = GuardrailDecision(
        passed=True,
        score=ranked_results[0].score if ranked_results else 0.0,
        threshold=settings.similarity_threshold,
    )
    response.latency = latency

    # Track RAG latency for live P50/P70/P100
    latency_tracker.record(latency.rag_ms)

    _log(query_id, transcript, ranked_results, winning_strategy, response.guardrail, latency, response.answer)

    return response


async def run_pipeline_text(query: str) -> PipelineResponse:
    """
    Text-only pipeline (no STT) — for benchmarking and testing.
    """
    query_id = uuid.uuid4().hex[:8]
    latency = LatencyBreakdown()
    response = PipelineResponse(transcript=query)

    # Pre-retrieval guardrail
    pre_check = guardrails.check_pre_retrieval(query)
    if not pre_check.passed:
        response.guardrail = pre_check
        response.latency = latency
        return response

    rag_start = time.perf_counter()

    # Embed
    t0 = time.perf_counter()
    query_embedding = embeddings.embed_query(query)
    latency.embedding_ms = round((time.perf_counter() - t0) * 1000, 2)

    # Retrieve
    t0 = time.perf_counter()
    raw_results = retrieval.hybrid_search(query=query, query_embedding=query_embedding, top_k=settings.top_k * 2)
    latency.retrieval_ms = round((time.perf_counter() - t0) * 1000, 2)

    # Rerank
    t0 = time.perf_counter()
    ranked, stats, winner = reranker.rerank_and_merge(raw_results, top_k=settings.top_k)
    latency.rerank_ms = round((time.perf_counter() - t0) * 1000, 2)
    response.strategy_stats = stats
    response.retrieved_chunks = ranked

    # Post-retrieval guardrail
    post_check = guardrails.check_post_retrieval(ranked)
    if not post_check.passed:
        response.guardrail = post_check
        latency.rag_ms = round((time.perf_counter() - rag_start) * 1000, 2)
        response.latency = latency
        return response

    # Generate
    t0 = time.perf_counter()
    gen_result = await generator.generate_answer(query, ranked)
    latency.generation_ms = round((time.perf_counter() - t0) * 1000, 2)
    response.answer = gen_result.answer
    response.citations = gen_result.citations

    # Groundedness
    t0 = time.perf_counter()
    g_check = await guardrails.check_groundedness(gen_result.answer, ranked)
    latency.guardrail_post_gen_ms = round((time.perf_counter() - t0) * 1000, 2)

    if not g_check.passed:
        response.answer = ""
        response.citations = []
        response.guardrail = g_check
    else:
        response.guardrail = GuardrailDecision(
            passed=True,
            score=ranked[0].score if ranked else 0.0,
            threshold=settings.similarity_threshold,
        )

    latency.rag_ms = round((time.perf_counter() - rag_start) * 1000, 2)
    latency.total_ms = latency.rag_ms
    response.latency = latency
    latency_tracker.record(latency.rag_ms)

    return response


def _log(query_id, transcript, results, winning_strategy, guardrail, latency, answer=""):
    """Log a structured query record."""
    log_query(
        query_id=query_id,
        transcript=transcript,
        retrieved_ids=[r.chunk_id for r in results[:5]],
        retrieved_scores=[r.score for r in results[:5]],
        winning_strategy=winning_strategy,
        guardrail_decision=guardrail.status.value,
        latency_breakdown=latency.model_dump(),
        answer_preview=answer,
    )
