"""
Convert an existing flat FAISS index to IVF for faster approximate search.

No re-ingest required — reads vectors from the current faiss.index on disk,
trains IVF clusters, and overwrites the index file. metadata.json is unchanged.

Usage:
    cd Task2/backend
    python -m scripts.rebuild_ivf_index
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import faiss
import numpy as np

from app.config import settings


def rebuild_ivf_index(index_dir: str | Path | None = None) -> None:
    index_dir = Path(index_dir or settings.index_dir)
    index_path = index_dir / "faiss.index"
    backup_path = index_dir / "faiss.index.flat.bak"

    if not index_path.exists():
        raise FileNotFoundError(f"No index at {index_path}. Run scripts.ingest first.")

    print("=" * 60)
    print("  FAISS Flat -> IVF Index Rebuild")
    print("=" * 60)
    print(f"   Index dir: {index_dir}")
    print(f"   nlist={settings.faiss_nlist}, nprobe={settings.faiss_nprobe}")

    index = faiss.read_index(str(index_path))
    n, d = index.ntotal, index.d
    print(f"   Loaded: {n:,} vectors, dim={d}, type={type(index).__name__}")

    if isinstance(index, faiss.IndexIVFFlat):
        index.nprobe = settings.faiss_nprobe
        faiss.write_index(index, str(index_path))
        print("   Index is already IVF — updated nprobe and saved.")
        return

    if n < settings.faiss_nlist * 40:
        print(
            f"   Corpus too small for IVF ({n} < {settings.faiss_nlist * 40}). "
            "Keeping flat index."
        )
        return

    print("   Extracting vectors from flat index...")
    vectors = index.reconstruct_n(0, n).astype(np.float32)

    print("   Training IVF index...")
    quantizer = faiss.IndexFlatIP(d)
    ivf_index = faiss.IndexIVFFlat(
        quantizer, d, settings.faiss_nlist, faiss.METRIC_INNER_PRODUCT
    )
    ivf_index.train(vectors)
    ivf_index.add(vectors)
    ivf_index.nprobe = settings.faiss_nprobe

    print(f"   Backing up flat index -> {backup_path.name}")
    shutil.copy2(index_path, backup_path)

    faiss.write_index(ivf_index, str(index_path))
    print(f"[OK] IVF index saved: {n:,} vectors -> {index_path}")


if __name__ == "__main__":
    rebuild_ivf_index()
