"""
Structured JSON logger for per-query observability.
Logs transcript, retrieved chunk IDs + scores, guardrail decisions, and latency
per stage — feeds both the latency report and retrieval debugging.
"""

import json
import logging
import sys
from datetime import datetime, timezone


def setup_logger(name: str = "rag_pipeline") -> logging.Logger:
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger

    logger.setLevel(logging.INFO)

    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(logging.INFO)

    formatter = logging.Formatter("%(message)s")
    handler.setFormatter(formatter)
    logger.addHandler(handler)

    return logger


logger = setup_logger()


def log_query(
    query_id: str,
    transcript: str,
    retrieved_ids: list[str],
    retrieved_scores: list[float],
    winning_strategy: str,
    guardrail_decision: str,
    latency_breakdown: dict,
    answer_preview: str = "",
):
    """Log a structured JSON record for a single query."""
    record = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "query_id": query_id,
        "transcript": transcript,
        "retrieved_chunks": [
            {"id": cid, "score": round(s, 4)}
            for cid, s in zip(retrieved_ids, retrieved_scores)
        ],
        "winning_strategy": winning_strategy,
        "guardrail": guardrail_decision,
        "latency": latency_breakdown,
        "answer_preview": answer_preview[:100] if answer_preview else "",
    }
    logger.info(json.dumps(record, ensure_ascii=True))
