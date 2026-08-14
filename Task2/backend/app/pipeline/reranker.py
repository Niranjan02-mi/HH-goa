"""
Merge & rerank results across chunking strategies.
Deduplicates overlapping chunks and logs which strategy wins per query.
"""

from __future__ import annotations

from collections import defaultdict

from app.models import RetrievalResult, ChunkStrategy, StrategyStats


def rerank_and_merge(
    results: list[RetrievalResult],
    top_k: int = 10,
) -> tuple[list[RetrievalResult], list[StrategyStats], str]:
    """
    Merge retrieval results across strategies:
    1. Deduplicate by passage_id (keep highest scoring)
    2. Sort by score descending
    3. Compute per-strategy stats

    Returns:
        - Reranked list of results (top_k)
        - Per-strategy stats
        - Winning strategy name
    """
    if not results:
        return [], [], ""

    # Deduplicate: if same passage_id appears from multiple strategies, keep highest score
    seen: dict[str, RetrievalResult] = {}
    for r in results:
        key = f"{r.passage_id}:{r.chunk_text[:50]}"
        if key not in seen or r.score > seen[key].score:
            seen[key] = r

    # Sort by score
    merged = sorted(seen.values(), key=lambda r: r.score, reverse=True)[:top_k]

    # For sentence-window chunks, expand text to window_context for generation
    for r in merged:
        if r.strategy == ChunkStrategy.SENTENCE_WINDOW and r.window_context:
            r.chunk_text = r.window_context

    # Per-strategy stats
    strategy_scores: dict[ChunkStrategy, list[float]] = defaultdict(list)
    for r in merged:
        strategy_scores[r.strategy].append(r.score)

    stats = []
    for strategy, scores in strategy_scores.items():
        stats.append(StrategyStats(
            strategy=strategy,
            avg_score=round(sum(scores) / len(scores), 4) if scores else 0.0,
            win_count=len(scores),
        ))

    # Winning strategy = strategy of the top-scoring result
    winning = merged[0].strategy.value if merged else ""

    return merged, stats, winning
