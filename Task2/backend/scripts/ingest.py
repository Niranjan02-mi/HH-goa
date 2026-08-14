"""
Offline ingestion pipeline:
1. Download MSMARCO-XI Hindi subset
2. Sample queries + extract passages
3. Clean & normalize
4. Apply 4 chunking strategies
5. Embed all chunks (BGE-M3 / multilingual-e5)
6. Build FAISS index with strategy tags

Run once before starting the demo:
    cd Task2/backend
    python -m scripts.ingest
"""

from __future__ import annotations

import json
import sys
import os
from pathlib import Path

# Add parent dir to path so we can import app modules
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np
from datasets import load_dataset

from app.config import settings
from app.pipeline.chunking import chunk_all_strategies
from app.pipeline.embeddings import embed_texts, embed_sentences_for_chunking
from app.pipeline.indexer import build_index
from app.models import Chunk


def main():
    print("=" * 60)
    print("  MSMARCO-XI Hindi  Offline Ingestion Pipeline")
    print("=" * 60)

    output_dir = Path(settings.index_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    #  Step 1: Load dataset
    print(f"\n[LOAD] Downloading MSMARCO-XI Hindi parquet from HuggingFace...")

    from itertools import islice
    from huggingface_hub import hf_hub_download
    import pyarrow.parquet as pq

    # Map language code to filename prefix
    lang_prefix_map = {"hi": "hin", "bn": "ben", "gu": "guj", "kn": "kan",
                       "ml": "mal", "mr": "mar", "or": "ori", "pa": "pan",
                       "ta": "tam", "te": "tel", "as": "asm", "ne": "nep"}
    lang_prefix = lang_prefix_map.get(settings.primary_language, settings.primary_language)
    parquet_filename = f"train/{lang_prefix}train.parquet"

    print(f"   Downloading {parquet_filename}...")
    local_path = hf_hub_download(
        repo_id="ai4bharat/MSMARCO-XI",
        filename=parquet_filename,
        repo_type="dataset",
    )
    print(f"   Downloaded to: {local_path}")

    # Read only the first N rows using pyarrow (avoid loading 3.7GB into memory)
    sample_size = settings.dataset_sample_size
    print(f"\n[SAMPLE] Reading first {sample_size} rows...")

    pf = pq.ParquetFile(local_path)
    sampled = []
    for batch in pf.iter_batches(batch_size=min(sample_size, 500)):
        df_batch = batch.to_pydict()
        for i in range(len(list(df_batch.values())[0])):
            row = {k: v[i] for k, v in df_batch.items()}
            sampled.append(row)
            if len(sampled) >= sample_size:
                break
        if len(sampled) >= sample_size:
            break

    print(f"   Collected {len(sampled)} rows")
    if len(sampled) > 0:
        print(f"   Fields: {list(sampled[0].keys())}")



    #  Step 3: Extract passages 
    print("\n [EXTRACT] Extracting passages...")
    passages = []  # list of (passage_text, passage_id, query_id, query_type)

    for idx, row in enumerate(sampled):
        query_id = str(idx)
        query_type = row.get("query_type", "")

        # Extract translated passages
        passages_data = row.get("passages", {})
        translated = passages_data.get("Translated_passages", [])
        is_selected = passages_data.get("is_selected", [])

        if not translated:
            continue

        for p_idx, passage_text in enumerate(translated):
            if not passage_text or not passage_text.strip():
                continue
            pid = f"P{idx}_{p_idx}"
            passages.append({
                "text": passage_text.strip(),
                "passage_id": pid,
                "query_id": query_id,
                "query_type": query_type,
                "is_selected": is_selected[p_idx] if p_idx < len(is_selected) else 0,
            })

    print(f"   Extracted {len(passages)} passages from {sample_size} queries")

    #  Step 4: Chunk all passages 
    print("\n  [CHUNK] Chunking passages (4 strategies)...")
    all_chunks: list[Chunk] = []
    embed_fn = embed_sentences_for_chunking  # For semantic chunking

    for i, p in enumerate(passages):
        if i % 500 == 0:
            print(f"   Processing passage {i}/{len(passages)}...")

        chunks = chunk_all_strategies(
            text=p["text"],
            passage_id=p["passage_id"],
            query_id=p["query_id"],
            query_type=p["query_type"],
            language=settings.primary_language,
            embed_fn=embed_fn,
        )
        all_chunks.extend(chunks)

    print(f"   Total chunks: {len(all_chunks)}")

    # Strategy breakdown
    from collections import Counter
    strategy_counts = Counter(c.strategy.value for c in all_chunks)
    for strat, count in sorted(strategy_counts.items()):
        print(f"     {strat}: {count}")

    #  Step 5: Embed all chunks 
    print(f"\n [EMBED] Embedding {len(all_chunks)} chunks with {settings.embedding_model}...")
    chunk_texts = [c.text for c in all_chunks]

    # Batch embed
    embeddings_array = embed_texts(chunk_texts, batch_size=64, show_progress=True)
    print(f"   [EMBED] Embedding shape: {embeddings_array.shape}")

    #  Step 6: Build FAISS index 
    print(f"\n  [INDEX] Building FAISS index...")
    build_index(all_chunks, embeddings_array, output_dir)

    #  Save query data for benchmarking 
    print("\n [SAVE] Saving query data for benchmarking...")
    queries = []
    for idx, row in enumerate(sampled):
        query_text = row.get("query", "")
        if query_text:
            queries.append({
                "query_id": str(idx),
                "query": query_text,
                "query_type": row.get("query_type", ""),
            })

    with open(output_dir / "queries.json", "w", encoding="utf-8") as f:
        json.dump(queries, f, ensure_ascii=False, indent=2)

    print(f"   Saved {len(queries)} queries")

    print("\n" + "=" * 60)
    print("   [DONE] Ingestion complete!")
    print(f"  Index dir: {output_dir.resolve()}")
    print("=" * 60)


if __name__ == "__main__":
    main()
