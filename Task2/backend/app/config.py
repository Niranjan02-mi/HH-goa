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
