"""
Application configuration via pydantic-settings.
All settings come from environment variables or .env file.
Language-configurable: change PRIMARY_LANGUAGE to switch the entire pipeline.
"""

from pathlib import Path
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # ── API keys ──────────────────────────────────────────────
    sarvam_api_key: str
    groq_api_key: str

    # ── Language ──────────────────────────────────────────────
    primary_language: str = "hi"

    # ── Retrieval ─────────────────────────────────────────────
    similarity_threshold: float = 0.55
    top_k: int = 10
    # BM25 (rank_bm25) does a pure-Python score pass over the whole corpus on
    # every query -- measured at ~380ms P50 / 200k chunks, dwarfing FAISS.
    # Off by default; flip on only once it's replaced with an indexed impl
    # (e.g. bm25s) or your corpus is small enough that it's cheap again.
    enable_bm25_hybrid: bool = False
    # "flat" = exact brute-force (IndexFlatIP). Fine under ~50k vectors.
    # "ivf"  = approximate (IndexIVFFlat) -- ~20x faster at 200k+ vectors,
    # small recall trade-off. Needs enough vectors to train nlist clusters.
    faiss_index_type: str = "flat"
    faiss_nlist: int = 200
    faiss_nprobe: int = 8

    # ── Generation ────────────────────────────────────────────
    generation_model: str = "llama-3.3-70b-versatile"
    max_gen_tokens: int = 256
    gen_temperature: float = 0.1

    # ── Embeddings ────────────────────────────────────────────
    embedding_model: str = "intfloat/multilingual-e5-large"

    # ── Data paths ────────────────────────────────────────────
    index_dir: str = "app/data"

    # ── Dataset ───────────────────────────────────────────────
    dataset_sample_size: int = 3000

    # ── Sarvam STT ────────────────────────────────────────────
    sarvam_stt_url: str = "https://api.sarvam.ai/speech-to-text"

    # ── Timeouts ──────────────────────────────────────────────
    stt_timeout: float = 10.0
    llm_timeout: float = 10.0

    @property
    def index_path(self) -> Path:
        return Path(self.index_dir)

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
