"""
Three-layer guardrail system:
1. Pre-retrieval: off-topic / unsafe query filter (regex + keyword)
2. Post-retrieval: confidence threshold on top similarity score
3. Post-generation: groundedness check (LLM self-check)
"""

from __future__ import annotations

import re

from app.config import settings
from app.models import (
    GuardrailDecision,
    GuardrailStatus,
    RetrievalResult,
)


# ── Layer 1: Pre-retrieval off-topic / unsafe filter ─────────

# Keywords/patterns that indicate unsafe or clearly off-topic queries
_UNSAFE_PATTERNS = [
    r"\b(kill|murder|bomb|attack|weapon|gun|poison)\b",
    r"\b(hack|exploit|crack|bypass)\b",
    r"\b(nude|porn|xxx|sex)\b",
    r"\b(password|credit.?card|ssn|social.?security)\b",
]

_UNSAFE_RE = re.compile("|".join(_UNSAFE_PATTERNS), re.IGNORECASE)


def check_pre_retrieval(transcript: str) -> GuardrailDecision:
    """
    Lightweight pre-retrieval check: reject obviously unsafe or
    too-short queries before wasting retrieval budget.
    """
    # Too short to be a real question
    text = transcript.strip()
    if len(text) < 3:
        return GuardrailDecision(
            passed=False,
            status=GuardrailStatus.BLOCKED_OFFTOPIC,
            reason="Query too short to process.",
        )

    # Unsafe content check
    if _UNSAFE_RE.search(text):
        return GuardrailDecision(
            passed=False,
            status=GuardrailStatus.BLOCKED_UNSAFE,
            reason="Query contains potentially unsafe content.",
        )

    return GuardrailDecision(passed=True)


# ── Layer 2: Post-retrieval confidence threshold ─────────────

def check_post_retrieval(results: list[RetrievalResult]) -> GuardrailDecision:
    """
    If the top retrieval score is below the threshold,
    skip generation — not enough grounded information.
    """
    if not results:
        return GuardrailDecision(
            passed=False,
            status=GuardrailStatus.BLOCKED_LOW_CONFIDENCE,
            reason="No relevant passages found.",
            score=0.0,
            threshold=settings.similarity_threshold,
        )

    top_score = results[0].score
    if top_score < settings.similarity_threshold:
        return GuardrailDecision(
            passed=False,
            status=GuardrailStatus.BLOCKED_LOW_CONFIDENCE,
            reason=f"Top retrieval score ({top_score:.3f}) below threshold ({settings.similarity_threshold}).",
            score=round(top_score, 4),
            threshold=settings.similarity_threshold,
        )

    return GuardrailDecision(
        passed=True,
        score=round(top_score, 4),
        threshold=settings.similarity_threshold,
    )


# ── Layer 3: Post-generation groundedness check ──────────────

async def check_groundedness(
    answer: str,
    chunks: list[RetrievalResult],
) -> GuardrailDecision:
    """
    Ask the LLM whether every claim in the answer traces to the
    provided context. Uses a fast, cheap call.

    Falls back to passed=True if the check itself fails (don't let
    the guardrail blow the latency budget on a flaky call).
    """
    try:
        from groq import AsyncGroq

        client = AsyncGroq(api_key=settings.groq_api_key)

        context = "\n".join([f"[{r.passage_id}]: {r.chunk_text[:200]}" for r in chunks])

        response = await client.chat.completions.create(
            model=settings.generation_model,  # Use main model instead of deprecated one
            messages=[
                {
                    "role": "system",
                    "content": "You verify groundedness. Given an answer and context passages, reply ONLY 'YES' if every claim in the answer is supported by the passages OR if the answer states that the information is not available. Reply 'NO: <reason>' if the answer makes unsupported claims.",
                },
                {
                    "role": "user",
                    "content": f"Context:\n{context}\n\nAnswer:\n{answer}\n\nIs the answer fully grounded in the context?",
                },
            ],
            max_tokens=50,
            temperature=0.0,
        )

        verdict = response.choices[0].message.content or ""
        verdict = verdict.strip().upper()

        if verdict.startswith("NO"):
            reason = verdict.replace("NO:", "").replace("NO", "").strip()
            return GuardrailDecision(
                passed=False,
                status=GuardrailStatus.BLOCKED_UNGROUNDED,
                reason=f"Answer not fully grounded: {reason}" if reason else "Answer not fully grounded in context.",
            )

        return GuardrailDecision(passed=True)

    except Exception:
        # Don't block on guardrail failure — prefer serving an answer
        return GuardrailDecision(passed=True, reason="Groundedness check skipped (error)")
