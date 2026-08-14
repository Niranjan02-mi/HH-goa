"""
Four chunking strategies for MSMARCO-XI passages.
Each produces tagged Chunk objects so retrieval quality per-strategy is measurable.
"""

from __future__ import annotations

import hashlib
import unicodedata
from typing import Optional

import re
import numpy as np
import tiktoken

from app.models import Chunk, ChunkStrategy


def _normalize(text: str) -> str:
    """Unicode NFC normalize + collapse whitespace."""
    text = unicodedata.normalize("NFC", text)
    text = " ".join(text.split())
    return text.strip()


def _make_id(strategy: str, passage_id: str, idx: int) -> str:
    """Deterministic chunk ID."""
    raw = f"{strategy}:{passage_id}:{idx}"
    return hashlib.md5(raw.encode()).hexdigest()[:12]


def _sentence_split(text: str) -> list[str]:
    """
    Split Hindi/English text into sentences cleanly without NLTK dependency.
    Handles Hindi Purna Viram (।), ?, !, ., and newlines.
    """
    sentences = re.split(r'(?<=[।?!.\n])\s+', text)
    return [s.strip() for s in sentences if s.strip()]



# ── Strategy 1: Fixed-size with overlap ──────────────────────

def chunk_fixed_size(
    text: str,
    passage_id: str = "",
    query_id: str = "",
    query_type: str = "",
    language: str = "hi",
    max_tokens: int = 256,
    overlap_frac: float = 0.15,
) -> list[Chunk]:
    """Split by token count with overlap."""
    text = _normalize(text)
    if not text:
        return []

    # Use cl100k_base tokenizer (robust, handles multilingual)
    enc = tiktoken.get_encoding("cl100k_base")
    tokens = enc.encode(text)
    overlap = int(max_tokens * overlap_frac)

    chunks = []
    start = 0
    idx = 0
    while start < len(tokens):
        end = min(start + max_tokens, len(tokens))
        chunk_tokens = tokens[start:end]
        chunk_text = enc.decode(chunk_tokens)

        chunks.append(Chunk(
            chunk_id=_make_id("fixed", passage_id, idx),
            text=chunk_text,
            strategy=ChunkStrategy.FIXED_SIZE,
            passage_id=passage_id,
            query_id=query_id,
            query_type=query_type,
            language=language,
        ))
        idx += 1
        start = end - overlap if end < len(tokens) else end

    return chunks


# ── Strategy 2: Semantic chunking ────────────────────────────

def chunk_semantic(
    text: str,
    passage_id: str = "",
    query_id: str = "",
    query_type: str = "",
    language: str = "hi",
    embed_fn=None,
    similarity_threshold: float = 0.5,
) -> list[Chunk]:
    """
    Split on embedding-similarity breakpoints between sentences.
    If no embed_fn provided, falls back to fixed-size chunking.
    """
    text = _normalize(text)
    if not text:
        return []

    sentences = _sentence_split(text)
    if len(sentences) <= 1:
        return [Chunk(
            chunk_id=_make_id("semantic", passage_id, 0),
            text=text,
            strategy=ChunkStrategy.SEMANTIC,
            passage_id=passage_id,
            query_id=query_id,
            query_type=query_type,
            language=language,
        )]

    if embed_fn is None:
        # Fallback: treat whole passage as one chunk
        return [Chunk(
            chunk_id=_make_id("semantic", passage_id, 0),
            text=text,
            strategy=ChunkStrategy.SEMANTIC,
            passage_id=passage_id,
            query_id=query_id,
            query_type=query_type,
            language=language,
        )]

    # Embed each sentence
    embeddings = embed_fn(sentences)
    if embeddings is None or len(embeddings) == 0:
        return [Chunk(
            chunk_id=_make_id("semantic", passage_id, 0),
            text=text,
            strategy=ChunkStrategy.SEMANTIC,
            passage_id=passage_id,
            query_id=query_id,
            query_type=query_type,
            language=language,
        )]

    # Find breakpoints where similarity drops
    breakpoints = []
    for i in range(len(embeddings) - 1):
        sim = float(np.dot(embeddings[i], embeddings[i + 1]) /
                     (np.linalg.norm(embeddings[i]) * np.linalg.norm(embeddings[i + 1]) + 1e-10))
        if sim < similarity_threshold:
            breakpoints.append(i + 1)

    # Split sentences at breakpoints
    chunks = []
    prev = 0
    for idx, bp in enumerate(breakpoints + [len(sentences)]):
        chunk_text = " ".join(sentences[prev:bp])
        if chunk_text.strip():
            chunks.append(Chunk(
                chunk_id=_make_id("semantic", passage_id, idx),
                text=chunk_text,
                strategy=ChunkStrategy.SEMANTIC,
                passage_id=passage_id,
                query_id=query_id,
                query_type=query_type,
                language=language,
            ))
        prev = bp

    return chunks if chunks else [Chunk(
        chunk_id=_make_id("semantic", passage_id, 0),
        text=text,
        strategy=ChunkStrategy.SEMANTIC,
        passage_id=passage_id,
        query_id=query_id,
        query_type=query_type,
        language=language,
    )]


# ── Strategy 3: Sentence-window ─────────────────────────────

def chunk_sentence_window(
    text: str,
    passage_id: str = "",
    query_id: str = "",
    query_type: str = "",
    language: str = "hi",
    window_size: int = 2,
) -> list[Chunk]:
    """
    Index single sentences, but store ±window_size neighboring
    sentences in window_context for retrieval-time expansion.
    """
    text = _normalize(text)
    if not text:
        return []

    sentences = _sentence_split(text)
    chunks = []

    for i, sent in enumerate(sentences):
        # Build window context: ±window_size neighbors
        start = max(0, i - window_size)
        end = min(len(sentences), i + window_size + 1)
        window = " ".join(sentences[start:end])

        chunks.append(Chunk(
            chunk_id=_make_id("window", passage_id, i),
            text=sent,
            strategy=ChunkStrategy.SENTENCE_WINDOW,
            passage_id=passage_id,
            query_id=query_id,
            query_type=query_type,
            language=language,
            window_context=window,
        ))

    return chunks


# ── Strategy 4: Metadata-aware ───────────────────────────────

def chunk_metadata_aware(
    text: str,
    passage_id: str = "",
    query_id: str = "",
    query_type: str = "",
    language: str = "hi",
    max_tokens: int = 256,
    overlap_frac: float = 0.15,
) -> list[Chunk]:
    """
    Same splitting as fixed-size, but enriched with full metadata
    (query_id, query_type, language) attached to every chunk for
    downstream filtering and reasoning.
    """
    text = _normalize(text)
    if not text:
        return []

    enc = tiktoken.get_encoding("cl100k_base")
    tokens = enc.encode(text)
    overlap = int(max_tokens * overlap_frac)

    chunks = []
    start = 0
    idx = 0
    while start < len(tokens):
        end = min(start + max_tokens, len(tokens))
        chunk_tokens = tokens[start:end]
        chunk_text = enc.decode(chunk_tokens)

        chunks.append(Chunk(
            chunk_id=_make_id("meta", passage_id, idx),
            text=chunk_text,
            strategy=ChunkStrategy.METADATA_AWARE,
            passage_id=passage_id,
            query_id=query_id,
            query_type=query_type,
            language=language,
        ))
        idx += 1
        start = end - overlap if end < len(tokens) else end

    return chunks


# ── Convenience: run all strategies on one passage ───────────

def chunk_all_strategies(
    text: str,
    passage_id: str = "",
    query_id: str = "",
    query_type: str = "",
    language: str = "hi",
    embed_fn=None,
) -> list[Chunk]:
    """Apply all four chunking strategies to a single passage text."""
    all_chunks = []
    all_chunks.extend(chunk_fixed_size(text, passage_id, query_id, query_type, language))
    all_chunks.extend(chunk_semantic(text, passage_id, query_id, query_type, language, embed_fn))
    all_chunks.extend(chunk_sentence_window(text, passage_id, query_id, query_type, language))
    all_chunks.extend(chunk_metadata_aware(text, passage_id, query_id, query_type, language))
    return all_chunks
