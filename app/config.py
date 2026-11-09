"""Environment-driven configuration."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / ".env")


def _f(name: str, default: float) -> float:
    return float(os.getenv(name, default))


@dataclass(frozen=True)
class Settings:
    llm_provider: str = field(default_factory=lambda: os.getenv("LLM_PROVIDER", "anthropic"))  # anthropic | stub
    model: str = field(default_factory=lambda: os.getenv("LLM_MODEL", "claude-haiku-5-5"))
    effort: str = field(default_factory=lambda: os.getenv("LLM_EFFORT", "low"))
    max_output_tokens: int = field(default_factory=lambda: int(os.getenv("LLM_MAX_OUTPUT_TOKENS", "4096")))
    # USD per million tokens (Claude Haiku 5.5 first-party list price, prompts <= 100K tokens)
    price_input: float = field(default_factory=lambda: _f("LLM_PRICE_INPUT_PER_MTOK", 0.10))
    price_output: float = field(default_factory=lambda: _f("LLM_PRICE_OUTPUT_PER_MTOK", 0.50))
    price_cache_write: float = field(default_factory=lambda: _f("LLM_PRICE_CACHE_WRITE_PER_MTOK", 0.125))
    price_cache_read: float = field(default_factory=lambda: _f("LLM_PRICE_CACHE_READ_PER_MTOK", 0.01))
    # hard cap on cumulative spend across all runs (persisted ledger)
    total_cost_cap_usd: float = field(default_factory=lambda: _f("TOTAL_COST_CAP_USD", 3.0))
    data_dir: Path = field(default_factory=lambda: Path(os.getenv("DATA_DIR", PROJECT_ROOT / "data")))
    results_dir: Path = field(default_factory=lambda: Path(os.getenv("RESULTS_DIR", PROJECT_ROOT / "results")))
    db_path: Path = field(default_factory=lambda: Path(os.getenv("DB_PATH", PROJECT_ROOT / "results" / "investigations.db")))
    log_level: str = field(default_factory=lambda: os.getenv("LOG_LEVEL", "INFO"))


def get_settings() -> Settings:
    return Settings()
