"""
LLM generation via Groq (Llama 3.1 70B at 500-2000+ tok/s).
Short prompt, short answer — every input token costs latency.
"""

from __future__ import annotations

from groq import AsyncGroq
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from app.config import settings
from app.models import RetrievalResult, GenerationResponse, Citation
from app.utils.latency import timed_ms

_client: AsyncGroq | None = None


def get_client() -> AsyncGroq:
    global _client
    if _client is None:
        _client = AsyncGroq(api_key=settings.groq_api_key)
    return _client


from app.pipeline.prompts import RAG_PROMPT, WEB_PROMPT, RAG_PLUS_WEB_PROMPT

def _build_rag_context(chunks: list[RetrievalResult]) -> str:
    parts = []
    for i, chunk in enumerate(chunks):
        pid = chunk.passage_id or f"P{i+1}"
        parts.append(f"[{pid}]: {chunk.chunk_text}")
    return "\n\n".join(parts)

def _build_web_context(web_results: list[dict]) -> str:
    parts = []
    for i, res in enumerate(web_results):
        parts.append(f"Source [{i+1}] {res['url']}:\n{res['snippet']}")
    return "\n\n".join(parts)

@retry(
    stop=stop_after_attempt(2),
    wait=wait_exponential(multiplier=0.3, min=0.3, max=1.0),
    retry=retry_if_exception_type(Exception),
    reraise=True,
)
async def generate_answer(
    query: str,
    language_name: str,
    route: str,
    chunks: list[RetrievalResult] = None,
    web_results: list[dict] = None,
) -> GenerationResponse:
    """Generate a grounded answer from retrieved chunks or web via Groq."""
    client = get_client()
    chunks = chunks or []
    web_results = web_results or []
    
    if route == "WEB":
        system_prompt = WEB_PROMPT
        context = _build_web_context(web_results)
        user_msg = f"Web results:\n{context}\n\nQuestion: {query}\n\nAnswer (cite URLs):"
    elif route == "RAG_PLUS_WEB":
        system_prompt = RAG_PLUS_WEB_PROMPT
        rag_context = _build_rag_context(chunks)
        web_context = _build_web_context(web_results)
        user_msg = f"DATASET SOURCES:\n{rag_context}\n\nWEB SOURCES:\n{web_context}\n\nQuestion: {query}\n\nAnswer (cite passage IDs and URLs):"
    else: # Default RAG
        system_prompt = RAG_PROMPT
        context = _build_rag_context(chunks)
        user_msg = f"Context passages:\n{context}\n\nQuestion: {query}\n\nAnswer (cite passage IDs):"

    lang_instruction = f"\nAnswer in {language_name}."

    with timed_ms() as timing:
        response = await client.chat.completions.create(
            model=settings.generation_model,
            messages=[
                {"role": "system", "content": system_prompt + lang_instruction},
                {"role": "user", "content": user_msg},
            ],
            max_tokens=settings.max_gen_tokens,
            temperature=settings.gen_temperature,
        )

    answer = response.choices[0].message.content or ""

    # Extract cited passage IDs and URLs
    import re
    citations = []
    
    # RAG citations
    cited_ids = list(set(re.findall(r'\[(P\d+(?:_\d+)?)\]', answer)))
    for pid in cited_ids:
        chunk_text = ""
        for c in chunks:
            if c.passage_id == pid:
                chunk_text = c.chunk_text[:200]
                break
        citations.append(Citation(passage_id=pid, chunk_text=chunk_text))
        
    # Web citations (heuristic extraction of URLs or Source [1])
    # To keep it simple, we check if URLs exist in answer
    for res in web_results:
        url = res["url"]
        if url in answer:
            citations.append(Citation(passage_id=url, chunk_text=res["snippet"][:200]))

    return GenerationResponse(
        answer=answer,
        citations=citations,
        latency_ms=timing["ms"],
    )

async def generate_answer_stream(
    query: str,
    language_name: str,
    route: str,
    chunks: list[RetrievalResult] = None,
    web_results: list[dict] = None,
):
    """Yield chunks of a grounded answer via Groq, returning citations at the end."""
    client = get_client()
    chunks = chunks or []
    web_results = web_results or []
    
    if route == "WEB":
        system_prompt = WEB_PROMPT
        context = _build_web_context(web_results)
        user_msg = f"Web results:\n{context}\n\nQuestion: {query}\n\nAnswer (cite URLs):"
    elif route == "RAG_PLUS_WEB":
        system_prompt = RAG_PLUS_WEB_PROMPT
        rag_context = _build_rag_context(chunks)
        web_context = _build_web_context(web_results)
        user_msg = f"DATASET SOURCES:\n{rag_context}\n\nWEB SOURCES:\n{web_context}\n\nQuestion: {query}\n\nAnswer (cite passage IDs and URLs):"
    else: # Default RAG
        system_prompt = RAG_PROMPT
        context = _build_rag_context(chunks)
        user_msg = f"Context passages:\n{context}\n\nQuestion: {query}\n\nAnswer (cite passage IDs):"

    lang_instruction = f"\nAnswer in {language_name}."

    response = await client.chat.completions.create(
        model=settings.generation_model,
        messages=[
            {"role": "system", "content": system_prompt + lang_instruction},
            {"role": "user", "content": user_msg},
        ],
        max_tokens=settings.max_gen_tokens,
        temperature=settings.gen_temperature,
        stream=True,
    )
    
    full_answer = ""
    async for chunk in response:
        delta = chunk.choices[0].delta.content
        if delta:
            full_answer += delta
            yield delta

    # Build citations from full_answer
    import re
    citations = []
    
    cited_ids = list(set(re.findall(r'\[(P\d+(?:_\d+)?)\]', full_answer)))
    for pid in cited_ids:
        chunk_text = ""
        for c in chunks:
            if c.passage_id == pid:
                chunk_text = c.chunk_text[:200]
                break
        citations.append(Citation(passage_id=pid, chunk_text=chunk_text))
        
    for res in web_results:
        url = res["url"]
        if url in full_answer:
            citations.append(Citation(passage_id=url, chunk_text=res["snippet"][:200]))

    # Yield citations as a dict at the very end
    yield {"citations": [c.model_dump() for c in citations]}
