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


import argparse

def parse_args():
    parser = argparse.ArgumentParser(description="Ingest MSMARCO-XI data.")
    parser.add_argument("--all-languages", action="store_true", help="Ingest all available languages.")
    parser.add_argument("--languages", type=str, help="Comma-separated list of languages (e.g. hi,mr,ta).")
    parser.add_argument("--language", type=str, help="Single language to ingest (e.g. hi).")
    return parser.parse_args()

def main():
    args = parse_args()
    print("=" * 60)
    print("  MSMARCO-XI Multilingual Offline Ingestion Pipeline")
    print("=" * 60)

    output_dir = Path(settings.index_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    lang_prefix_map = {
        "as": "asm", "bn": "ben", "gu": "guj", "hi": "hin",
        "kn": "kan", "ml": "mal", "mr": "mar", "ne": "nep",
        "or": "ori", "pa": "pan", "ta": "tam", "te": "tel", "ur": "urd"
    }

    if args.all_languages:
        langs = list(lang_prefix_map.keys())
    elif args.languages:
        langs = [l.strip() for l in args.languages.split(",")]
    elif args.language:
        langs = [args.language]
    else:
        langs = [settings.primary_language]  # Fallback

    print(f"Ingesting languages: {langs}")

    from itertools import islice
    from huggingface_hub import hf_hub_download
    import pyarrow.parquet as pq

    sampled = []
    
    for lang in langs:
        lang_prefix = lang_prefix_map.get(lang)
        if not lang_prefix:
            print(f"Warning: Unknown language {lang}, skipping.")
            continue

        parquet_filename = f"train/{lang_prefix}train.parquet"
        print(f"\n[LOAD] Downloading MSMARCO-XI {lang} parquet from HuggingFace...")

        try:
            local_path = hf_hub_download(
                repo_id="ai4bharat/MSMARCO-XI",
                filename=parquet_filename,
                repo_type="dataset",
            )
            print(f"   Downloaded {lang} to: {local_path}")
            
            sample_size = settings.dataset_sample_size
            print(f"   [SAMPLE] Reading first {sample_size} rows for {lang}...")
            
            pf = pq.ParquetFile(local_path)
            lang_sampled = 0
            for batch in pf.iter_batches(batch_size=min(sample_size, 500)):
                df_batch = batch.to_pydict()
                for i in range(len(list(df_batch.values())[0])):
                    row = {k: v[i] for k, v in df_batch.items()}
                    row['_language'] = lang
                    row['_language_name'] = lang_prefix_map.get(lang).capitalize() # Just as a placeholder name
                    sampled.append(row)
                    lang_sampled += 1
                    if lang_sampled >= sample_size:
                        break
                if lang_sampled >= sample_size:
                    break
            print(f"   Collected {lang_sampled} rows for {lang}")
        except Exception as e:
            print(f"   Failed to download {lang}: {e}")

    print(f"\n   Total Collected rows: {len(sampled)}")

    #  Step 3: Extract passages 
    print("\n [EXTRACT] Extracting passages...")
    passages = []  # list of (passage_text, passage_id, query_id, query_type)

    for idx, row in enumerate(sampled):
        query_id = str(idx)
        query_type = row.get("query_type", "")
        language = row.get("_language", "en")
        language_name = row.get("_language_name", "")

        # Extract translated passages
        passages_data = row.get("passages", {})
        translated = passages_data.get("Translated_passages", [])
        is_selected = passages_data.get("is_selected", [])
        english_passages = passages_data.get("passage_text", []) # Original english text

        if not translated:
            continue

        for p_idx, passage_text in enumerate(translated):
            if not passage_text or not passage_text.strip():
                continue
            pid = f"P{idx}_{p_idx}"
            passages.append({
                "text": passage_text.strip(),
                "english_text": english_passages[p_idx] if p_idx < len(english_passages) else "",
                "passage_id": pid,
                "query_id": query_id,
                "query_type": query_type,
                "is_selected": is_selected[p_idx] if p_idx < len(is_selected) else 0,
                "language": language,
                "language_name": language_name,
                "source_lang": "en",
                "target_lang": language,
                "passage_index": p_idx
            })

    print(f"   Extracted {len(passages)} passages from {len(sampled)} queries")

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
            language=p["language"],
            embed_fn=embed_fn,
        )
        # Update extra metadata for each chunk
        for c in chunks:
            c.language = p["language"]
            c.language_name = p["language_name"]
            c.source_lang = p["source_lang"]
            c.target_lang = p["target_lang"]
            c.english_text = p["english_text"]
            c.passage_index = p["passage_index"]
            c.is_selected = p["is_selected"]

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
                "language": row.get("_language", "")
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
