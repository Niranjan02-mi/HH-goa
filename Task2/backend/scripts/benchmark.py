"""
P50/P70/P100 latency benchmark harness.
Runs real queries through the retrieval+generation pipeline
and reports percentile latencies.

Usage:
    cd Task2/backend
    python -m scripts.benchmark
"""

from __future__ import annotations

import asyncio
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np

from app.config import settings
from app.pipeline import retrieval, embeddings
from app.pipeline.orchestrator import run_pipeline_text


async def main():
    print("=" * 60)
    print("  Voice RAG — Latency Benchmark")
    print("=" * 60)

    # Load index
    retrieval.init_retrieval(settings.index_dir)

    # Pre-load embedding model
    embeddings.get_model()

    # Load queries
    queries_path = Path(settings.index_dir) / "queries.json"
    if not queries_path.exists():
        print("❌ queries.json not found. Run ingest.py first.")
        return

    with open(queries_path, "r", encoding="utf-8") as f:
        all_queries = json.load(f)

    # Sample queries for benchmark
    sample_size = min(200, len(all_queries))
    sample_queries = all_queries[:sample_size]
    print(f"\n📊 Running benchmark with {sample_size} queries...")
    print(f"   Model: {settings.generation_model}")
    print(f"   Threshold: {settings.similarity_threshold}")

    latencies = []
    retrieval_latencies = []
    generation_latencies = []
    embedding_latencies = []
    strategy_wins = {}
    guardrail_blocks = 0

    for i, q in enumerate(sample_queries):
        if i % 20 == 0:
            print(f"   Query {i}/{sample_size}...")

        try:
            result = await run_pipeline_text(q["query"])
            lat = result.latency

            latencies.append(lat.rag_ms)
            retrieval_latencies.append(lat.retrieval_ms)
            generation_latencies.append(lat.generation_ms)
            embedding_latencies.append(lat.embedding_ms)

            # Track strategy wins
            for stat in result.strategy_stats:
                wins = strategy_wins.get(stat.strategy.value, 0)
                strategy_wins[stat.strategy.value] = wins + stat.win_count

            if not result.guardrail.passed:
                guardrail_blocks += 1

        except Exception as e:
            print(f"   ⚠️  Query {i} failed: {e}")
            continue

    if not latencies:
        print("❌ No successful queries. Check your setup.")
        return

    # ── Results ───────────────────────────────────────────────
    lat = np.array(latencies)
    ret = np.array(retrieval_latencies)
    gen = np.array(generation_latencies)
    emb = np.array(embedding_latencies)

    print("\n" + "=" * 60)
    print("  📈 BENCHMARK RESULTS")
    print("=" * 60)

    print(f"\n  Queries: {len(latencies)}/{sample_size} successful")
    print(f"  Guardrail blocks: {guardrail_blocks}")

    print(f"\n  ── RAG Latency (embed + retrieve + generate) ──")
    print(f"  P50:  {np.percentile(lat, 50):>8.1f} ms")
    print(f"  P70:  {np.percentile(lat, 70):>8.1f} ms")
    print(f"  P100: {np.percentile(lat, 100):>8.1f} ms")
    print(f"  Mean: {np.mean(lat):>8.1f} ms")

    print(f"\n  ── Embedding Latency ──")
    print(f"  P50:  {np.percentile(emb, 50):>8.1f} ms")
    print(f"  P100: {np.percentile(emb, 100):>8.1f} ms")

    print(f"\n  ── Retrieval Latency ──")
    print(f"  P50:  {np.percentile(ret, 50):>8.1f} ms")
    print(f"  P100: {np.percentile(ret, 100):>8.1f} ms")

    print(f"\n  ── Generation Latency ──")
    print(f"  P50:  {np.percentile(gen, 50):>8.1f} ms")
    print(f"  P100: {np.percentile(gen, 100):>8.1f} ms")

    print(f"\n  ── Strategy Win Rates ──")
    total_wins = sum(strategy_wins.values()) or 1
    for strat, wins in sorted(strategy_wins.items(), key=lambda x: -x[1]):
        pct = wins / total_wins * 100
        print(f"  {strat:>20s}: {wins:>4d} wins ({pct:.1f}%)")

    # Save results
    results = {
        "queries_total": sample_size,
        "queries_successful": len(latencies),
        "guardrail_blocks": guardrail_blocks,
        "rag_latency": {
            "p50_ms": round(float(np.percentile(lat, 50)), 1),
            "p70_ms": round(float(np.percentile(lat, 70)), 1),
            "p100_ms": round(float(np.percentile(lat, 100)), 1),
            "mean_ms": round(float(np.mean(lat)), 1),
        },
        "strategy_wins": strategy_wins,
    }

    output_path = Path(settings.index_dir) / "benchmark_results.json"
    with open(output_path, "w") as f:
        json.dump(results, f, indent=2)
    print(f"\n  📁 Results saved to {output_path}")


if __name__ == "__main__":
    asyncio.run(main())
