"""
FAISS index builder (offline pipeline).
Builds a single flat inner-product index from all chunk embeddings,
with a parallel metadata store mapping vector indices to Chunk objects.
"""

from __future__ import annotations

import json
from pathlib import Path

import faiss
import numpy as np

from app.config import settings
from app.models import Chunk


def build_index(
    chunks: list[Chunk],
    embeddings: np.ndarray,
    output_dir: str | Path,
) -> None:
    """
    Build and save a FAISS index + metadata JSON.

    Args:
        chunks: list of Chunk objects (one per embedding row)
        embeddings: (N, D) float32 array, L2-normalized
        output_dir: directory to write faiss.index and metadata.json
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    n, d = embeddings.shape
    assert n == len(chunks), f"Mismatch: {n} embeddings vs {len(chunks)} chunks"

    if settings.faiss_index_type == "ivf" and n >= settings.faiss_nlist * 40:
        # Approximate search — measured ~20x faster than flat at 200k vectors.
        # Needs enough vectors per cluster (nlist) to train meaningfully, so
        # this only kicks in once the corpus is actually large enough for it
        # to matter; small corpora fall through to flat below.
        quantizer = faiss.IndexFlatIP(d)
        index = faiss.IndexIVFFlat(quantizer, d, settings.faiss_nlist, faiss.METRIC_INNER_PRODUCT)
        index.train(embeddings)
        index.nprobe = settings.faiss_nprobe
    else:
        # Exact brute-force inner-product search (cosine similarity on
        # L2-normed vectors). Simple and exact, but scales linearly with
        # corpus size — measured ~62ms P50 at 200k vectors on CPU, so it
        # stops being "basically free" well before you'd expect.
        index = faiss.IndexFlatIP(d)
    index.add(embeddings)

    # Save FAISS index
    faiss.write_index(index, str(output_dir / "faiss.index"))

    # Save metadata — one JSON object per chunk, keyed by vector index
    metadata = []
    for i, chunk in enumerate(chunks):
        metadata.append(chunk.model_dump())

    with open(output_dir / "metadata.json", "w", encoding="utf-8") as f:
        json.dump(metadata, f, ensure_ascii=False, indent=None)

    print(f"[OK] Index saved: {n} vectors, dim={d}")
    print(f"   -> {output_dir / 'faiss.index'}")
    print(f"   -> {output_dir / 'metadata.json'}")


def load_index(index_dir: str | Path) -> tuple[faiss.Index, list[dict]]:
    """Load FAISS index + metadata from disk."""
    index_dir = Path(index_dir)
    index = faiss.read_index(str(index_dir / "faiss.index"))

    # nprobe is a runtime search param -- reapply explicitly on load rather
    # than trust it round-tripped through the serialized index.
    if hasattr(index, "nprobe"):
        index.nprobe = settings.faiss_nprobe

    with open(index_dir / "metadata.json", "r", encoding="utf-8") as f:
        metadata = json.load(f)

    return index, metadata
