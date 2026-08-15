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

    # ── Retrieval ─────────────────────────────────────────────
    similarity_threshold: float = 0.55
    top_k: int = 10

    # ── LLM Config ──────────────────────────────────────────────
    llm_provider: str = "groq"
    generation_model: str = "llama-3.1-8b-instant"
    max_gen_tokens: int = 512
    gen_temperature: float = 0.1

    # ── Web Search ────────────────────────────────────────────
    web_search_provider: str = "tavily"
    web_search_api_key: str = ""

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
        extra = "ignore"


settings = Settings()
