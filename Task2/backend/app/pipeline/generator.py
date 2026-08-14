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


def _build_context(chunks: list[RetrievalResult]) -> str:
    """Format retrieved chunks as numbered passages for the LLM."""
    parts = []
    for i, chunk in enumerate(chunks):
        pid = chunk.passage_id or f"P{i+1}"
        parts.append(f"[{pid}]: {chunk.chunk_text}")
    return "\n\n".join(parts)


SYSTEM_PROMPT = """You are a factual assistant. Answer the user's question ONLY using the provided context passages. Follow these rules strictly:
1. Cite passage IDs like [P1], [P2] for every claim.
2. If the context doesn't contain the answer, say: "इस संदर्भ में यह जानकारी उपलब्ध नहीं है।" (This information is not available in the context.)
3. Keep your answer concise — 2-4 sentences maximum.
4. Answer in the same language as the question."""


@retry(
    stop=stop_after_attempt(2),
    wait=wait_exponential(multiplier=0.3, min=0.3, max=1.0),
    retry=retry_if_exception_type(Exception),
    reraise=True,
)
async def generate_answer(
    query: str,
    chunks: list[RetrievalResult],
) -> GenerationResponse:
    """Generate a grounded answer from retrieved chunks via Groq."""
    client = get_client()
    context = _build_context(chunks)

    user_msg = f"""Context passages:
{context}

Question: {query}

Answer (cite passage IDs):"""

    with timed_ms() as timing:
        response = await client.chat.completions.create(
            model=settings.generation_model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_msg},
            ],
            max_tokens=settings.max_gen_tokens,
            temperature=settings.gen_temperature,
        )

    answer = response.choices[0].message.content or ""

    # Extract cited passage IDs from answer
    import re
    cited_ids = list(set(re.findall(r'\[([^\]]+)\]', answer)))

    citations = []
    for pid in cited_ids:
        # Find the matching chunk text
        chunk_text = ""
        for c in chunks:
            cpid = c.passage_id or ""
            if cpid == pid:
                chunk_text = c.chunk_text[:200]
                break
        citations.append(Citation(passage_id=pid, chunk_text=chunk_text))

    return GenerationResponse(
        answer=answer,
        citations=citations,
        latency_ms=timing["ms"],
    )
