"""Configuration - SQLite for local, PostgreSQL for Railway/Render."""
import os
from dotenv import load_dotenv
load_dotenv()

_raw = os.getenv("DATABASE_URL", "sqlite:///./storyteller.db")
# Render/Railway use postgres://; SQLAlchemy 2.x wants postgresql://
DATABASE_URL = _raw.replace("postgres://", "postgresql://", 1) if _raw.startswith("postgres://") else _raw

JUDGE_PROVIDER = os.getenv("JUDGE_PROVIDER", "").strip().lower()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
