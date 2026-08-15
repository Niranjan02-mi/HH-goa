"""
End-to-end pipeline orchestrator.
Wires: audio → STT → guardrail_pre → embed → retrieve → rerank →
       guardrail_post_retrieval → generate → guardrail_post_gen → response
Instruments every stage with perf_counter for the latency breakdown.
"""

from __future__ import annotations

import time
import uuid
import asyncio

from app.config import settings
from app.models import (
    PipelineResponse,
    LatencyBreakdown,
    GuardrailDecision,
    GuardrailStatus,
)
from app.pipeline import stt, retrieval, generator, guardrails, reranker, embeddings, language, router, web_search, llm
from app.utils.latency import latency_tracker
from app.utils.logger import log_query

async def run_pipeline(audio_bytes: bytes) -> PipelineResponse:
    query_id = uuid.uuid4().hex[:8]
    latency = LatencyBreakdown()
    response = PipelineResponse()

    # ── STT ────────────────────────────────
    try:
        t0 = time.perf_counter()
        stt_result = await stt.transcribe(audio_bytes)
        latency.stt_ms = round((time.perf_counter() - t0) * 1000, 2)
        response.transcript = stt_result.transcript
    except Exception as e:
        response.guardrail = GuardrailDecision(passed=False, status=GuardrailStatus.BLOCKED_OFFTOPIC, reason=f"Speech-to-text failed: {str(e)}")
        response.latency = latency
        return response

    transcript = stt_result.transcript
    if not transcript.strip():
        response.guardrail = GuardrailDecision(passed=False, status=GuardrailStatus.BLOCKED_OFFTOPIC, reason="Could not detect speech.")
        response.latency = latency
        return response

    return await _process_transcript(transcript, query_id, latency, response)

async def run_pipeline_text(query: str) -> PipelineResponse:
    query_id = uuid.uuid4().hex[:8]
    latency = LatencyBreakdown()
    response = PipelineResponse(transcript=query)
    return await _process_transcript(query, query_id, latency, response)

async def _process_transcript(transcript: str, query_id: str, latency: LatencyBreakdown, response: PipelineResponse) -> PipelineResponse:
    # ── Language Detection ───────────────────────
    lang_info = language.detect_language(transcript)
    lang_code = lang_info["code"]
    lang_name = lang_info["name"]
    response.language_name = lang_name

    # ── Pre-retrieval guardrail ───────────────────────
    t0 = time.perf_counter()
    pre_check = guardrails.check_pre_retrieval(transcript)
    latency.guardrail_pre_ms = round((time.perf_counter() - t0) * 1000, 2)

    if not pre_check.passed:
        response.guardrail = pre_check
        response.latency = latency
        return response

    # ── Routing & Preemptive Retrieval (Parallel) ────
    t0_route = time.perf_counter()
    route_task = asyncio.create_task(router.route_query(transcript))
    
    # Preemptively do local CPU-bound embedding and retrieval while waiting for I/O
    t0_embed = time.perf_counter()
    query_embedding = embeddings.embed_query(transcript)
    latency.embedding_ms = round((time.perf_counter() - t0_embed) * 1000, 2)
    
    t0_ret = time.perf_counter()
    raw_results = retrieval.hybrid_search(query=transcript, query_embedding=query_embedding, top_k=settings.top_k * 2)
    latency.retrieval_ms = round((time.perf_counter() - t0_ret) * 1000, 2)
    
    # Await routing if not already finished
    route_decision = await route_task
    latency.route_ms = round((time.perf_counter() - t0_route) * 1000, 2)
    
    route = route_decision["route"]
    response.route = route

    rag_start = time.perf_counter()

    # ── Execute Route ────────────────────────────────
    if route == "GENERAL_LLM":
        try:
            t0 = time.perf_counter()
            ans, gen_ms = await llm.generate_general_answer(transcript, lang_name)
            latency.generation_ms = gen_ms
            response.answer = ans
            response.guardrail = GuardrailDecision(passed=True)
        except Exception as e:
            response.guardrail = GuardrailDecision(passed=False, status=GuardrailStatus.BLOCKED_OFFTOPIC, reason=f"Generation failed: {str(e)}")
        
        latency.rag_ms = round((time.perf_counter() - rag_start) * 1000, 2)
        latency.total_ms = round(latency.stt_ms + latency.guardrail_pre_ms + latency.route_ms + latency.rag_ms, 2)
        response.latency = latency
        _log(query_id, transcript, [], "", response.guardrail, latency, response.answer)
        return response

    web_results = []
    if route in ["WEB", "RAG_PLUS_WEB"]:
        t0 = time.perf_counter()
        web_results, web_ms = await web_search.perform_web_search(transcript)
        latency.web_search_ms = web_ms
        response.web_results = web_results

    ranked_results = []
    winning_strategy = ""
    
    if route in ["RAG", "RAG_PLUS_WEB"]:
        # Rerank the preemptively retrieved results
        t0 = time.perf_counter()
        ranked_results, stats, winning_strategy = reranker.rerank_and_merge(raw_results, top_k=settings.top_k)
        latency.rerank_ms = round((time.perf_counter() - t0) * 1000, 2)
        response.strategy_stats = stats
        response.retrieved_chunks = ranked_results

        # Post-retrieval guardrail (Only block if we have no web results to fall back on)
        t0 = time.perf_counter()
        post_ret_check = guardrails.check_post_retrieval(ranked_results)
        latency.guardrail_post_retrieval_ms = round((time.perf_counter() - t0) * 1000, 2)

        if not post_ret_check.passed and route == "RAG":
            # Phase 9: Return an abstained answer in the user's language
            response.guardrail = post_ret_check
            response.answer = f"मुझे इस सवाल का जवाब देने के लिए पर्याप्त जानकारी नहीं मिली।" if lang_code == "hi" else "I could not find sufficient information to answer this question."
            latency.rag_ms = round((time.perf_counter() - rag_start) * 1000, 2)
            response.latency = latency
            _log(query_id, transcript, ranked_results, winning_strategy, post_ret_check, latency)
            return response

    # ── Generate answer ───────────────────────────────
    try:
        t0 = time.perf_counter()
        gen_result = await generator.generate_answer(transcript, lang_name, route, chunks=ranked_results, web_results=web_results)
        latency.generation_ms = round((time.perf_counter() - t0) * 1000, 2)
        response.answer = gen_result.answer
        response.citations = gen_result.citations
    except Exception as e:
        response.guardrail = GuardrailDecision(passed=False, status=GuardrailStatus.BLOCKED_OFFTOPIC, reason=f"Generation failed: {str(e)}")
        latency.rag_ms = round((time.perf_counter() - rag_start) * 1000, 2)
        response.latency = latency
        return response

    # ── Post-generation groundedness check ────────────
    # Only if it relies on RAG chunks
    if route in ["RAG", "RAG_PLUS_WEB"] and ranked_results:
        t0 = time.perf_counter()
        ground_check = await guardrails.check_groundedness(gen_result.answer, ranked_results)
        latency.guardrail_post_gen_ms = round((time.perf_counter() - t0) * 1000, 2)

        if not ground_check.passed:
            response.answer = "मुझे क्षमा करें, मैं इस प्रश्न का सटीक उत्तर देने में असमर्थ हूँ।" if lang_code == "hi" else "I'm sorry, I am unable to provide an accurate answer to this question."
            response.citations = []
            response.guardrail = ground_check
            latency.rag_ms = round((time.perf_counter() - rag_start) * 1000, 2)
            response.latency = latency
            _log(query_id, transcript, ranked_results, winning_strategy, ground_check, latency)
            return response

    # ── All checks passed ─────────────────────────────────────
    latency.rag_ms = round((time.perf_counter() - rag_start) * 1000, 2)
    latency.total_ms = round(latency.stt_ms + latency.guardrail_pre_ms + latency.route_ms + latency.web_search_ms + latency.rag_ms, 2)
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

import json

async def run_pipeline_stream(audio_bytes: bytes):
    query_id = uuid.uuid4().hex[:8]
    latency = LatencyBreakdown()
    response = PipelineResponse()

    # ── STT ────────────────────────────────
    try:
        t0 = time.perf_counter()
        stt_result = await stt.transcribe(audio_bytes)
        latency.stt_ms = round((time.perf_counter() - t0) * 1000, 2)
        transcript = stt_result.transcript
    except Exception as e:
        yield f"event: error\ndata: {json.dumps({'error': 'Speech-to-text failed', 'detail': str(e)})}\n\n"
        return

    if not transcript.strip():
        yield f"event: error\ndata: {json.dumps({'error': 'Could not detect speech'})}\n\n"
        return

    async for chunk in _process_transcript_stream(transcript, query_id, latency, response):
        yield chunk

async def run_pipeline_text_stream(query: str):
    query_id = uuid.uuid4().hex[:8]
    latency = LatencyBreakdown()
    response = PipelineResponse(transcript=query)
    async for chunk in _process_transcript_stream(query, query_id, latency, response):
        yield chunk

async def _process_transcript_stream(transcript: str, query_id: str, latency: LatencyBreakdown, response: PipelineResponse):
    # ── Language Detection ───────────────────────
    lang_info = language.detect_language(transcript)
    lang_code = lang_info["code"]
    lang_name = lang_info["name"]
    response.language_name = lang_name

    # ── Pre-retrieval guardrail ───────────────────────
    t0 = time.perf_counter()
    pre_check = guardrails.check_pre_retrieval(transcript)
    latency.guardrail_pre_ms = round((time.perf_counter() - t0) * 1000, 2)

    if not pre_check.passed:
        yield f"event: error\ndata: {json.dumps({'error': 'Blocked by guardrail (pre-retrieval)'})}\n\n"
        return

    # ── Routing & Preemptive Retrieval (Parallel) ────
    t0_route = time.perf_counter()
    route_task = asyncio.create_task(router.route_query(transcript))
    
    t0_embed = time.perf_counter()
    query_embedding = embeddings.embed_query(transcript)
    latency.embedding_ms = round((time.perf_counter() - t0_embed) * 1000, 2)
    
    t0_ret = time.perf_counter()
    raw_results = retrieval.hybrid_search(query=transcript, query_embedding=query_embedding, top_k=settings.top_k * 2)
    latency.retrieval_ms = round((time.perf_counter() - t0_ret) * 1000, 2)
    
    route_decision = await route_task
    latency.route_ms = round((time.perf_counter() - t0_route) * 1000, 2)
    
    route = route_decision["route"]
    response.route = route

    # Yield metadata event to UI
    yield f"event: metadata\ndata: {json.dumps({'transcript': transcript, 'route': route, 'language': lang_name})}\n\n"

    rag_start = time.perf_counter()

    # ── Execute Route ────────────────────────────────
    if route == "GENERAL_LLM":
        try:
            t0 = time.perf_counter()
            full_ans = ""
            async for chunk in llm.generate_general_answer_stream(transcript, lang_name):
                full_ans += chunk
                yield f"event: chunk\ndata: {json.dumps({'text': chunk})}\n\n"
            latency.generation_ms = round((time.perf_counter() - t0) * 1000, 2)
            response.answer = full_ans
            response.guardrail = GuardrailDecision(passed=True)
        except Exception as e:
            yield f"event: error\ndata: {json.dumps({'error': f'Generation failed: {str(e)}'})}\n\n"
            return
        
        latency.rag_ms = round((time.perf_counter() - rag_start) * 1000, 2)
        latency.total_ms = round(latency.stt_ms + latency.guardrail_pre_ms + latency.route_ms + latency.rag_ms, 2)
        response.latency = latency
        _log(query_id, transcript, [], "", response.guardrail, latency, response.answer)
        
        yield f"event: end\ndata: {json.dumps({'latency': latency.model_dump(), 'citations': []})}\n\n"
        return

    web_results = []
    if route in ["WEB", "RAG_PLUS_WEB"]:
        t0 = time.perf_counter()
        web_results, web_ms = await web_search.perform_web_search(transcript)
        latency.web_search_ms = web_ms
        response.web_results = web_results

    ranked_results = []
    winning_strategy = ""
    
    if route in ["RAG", "RAG_PLUS_WEB"]:
        t0 = time.perf_counter()
        ranked_results, stats, winning_strategy = reranker.rerank_and_merge(raw_results, top_k=settings.top_k)
        latency.rerank_ms = round((time.perf_counter() - t0) * 1000, 2)
        response.strategy_stats = stats
        response.retrieved_chunks = ranked_results

        t0 = time.perf_counter()
        post_ret_check = guardrails.check_post_retrieval(ranked_results)
        latency.guardrail_post_retrieval_ms = round((time.perf_counter() - t0) * 1000, 2)

        if not post_ret_check.passed and route == "RAG":
            ans = "मुझे इस सवाल का जवाब देने के लिए पर्याप्त जानकारी नहीं मिली।" if lang_code == "hi" else "I could not find sufficient information to answer this question."
            yield f"event: chunk\ndata: {json.dumps({'text': ans})}\n\n"
            latency.rag_ms = round((time.perf_counter() - rag_start) * 1000, 2)
            response.latency = latency
            _log(query_id, transcript, ranked_results, winning_strategy, post_ret_check, latency)
            yield f"event: end\ndata: {json.dumps({'latency': latency.model_dump(), 'citations': []})}\n\n"
            return

    # ── Generate answer ───────────────────────────────
    try:
        t0 = time.perf_counter()
        full_ans = ""
        citations = []
        async for item in generator.generate_answer_stream(transcript, lang_name, route, chunks=ranked_results, web_results=web_results):
            if isinstance(item, str):
                full_ans += item
                yield f"event: chunk\ndata: {json.dumps({'text': item})}\n\n"
            elif isinstance(item, dict) and "citations" in item:
                citations = item["citations"]
        
        latency.generation_ms = round((time.perf_counter() - t0) * 1000, 2)
        response.answer = full_ans
        response.citations = citations
    except Exception as e:
        yield f"event: error\ndata: {json.dumps({'error': f'Generation failed: {str(e)}'})}\n\n"
        return

    # ── Post-generation groundedness check ────────────
    if route in ["RAG", "RAG_PLUS_WEB"] and ranked_results:
        t0 = time.perf_counter()
        ground_check = await guardrails.check_groundedness(response.answer, ranked_results)
        latency.guardrail_post_gen_ms = round((time.perf_counter() - t0) * 1000, 2)

        if not ground_check.passed:
            err_msg = "मुझे क्षमा करें, मैं इस प्रश्न का सटीक उत्तर देने में असमर्थ हूँ।" if lang_code == "hi" else "I'm sorry, I am unable to provide an accurate answer to this question."
            yield f"event: error\ndata: {json.dumps({'error': err_msg})}\n\n"
            latency.rag_ms = round((time.perf_counter() - rag_start) * 1000, 2)
            _log(query_id, transcript, ranked_results, winning_strategy, ground_check, latency)
            return

    # ── All checks passed ─────────────────────────────────────
    latency.rag_ms = round((time.perf_counter() - rag_start) * 1000, 2)
    latency.total_ms = round(latency.stt_ms + latency.guardrail_pre_ms + latency.route_ms + latency.web_search_ms + latency.rag_ms, 2)
    response.guardrail = GuardrailDecision(
        passed=True,
        score=ranked_results[0].score if ranked_results else 0.0,
        threshold=settings.similarity_threshold,
    )
    
    latency_tracker.record(latency.rag_ms)
    _log(query_id, transcript, ranked_results, winning_strategy, response.guardrail, latency, response.answer)

    yield f"event: end\ndata: {json.dumps({'latency': latency.model_dump(), 'citations': citations})}\n\n"
