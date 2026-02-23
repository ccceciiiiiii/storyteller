"""Configuration - SQLite for local, PostgreSQL for Railway/Render."""
import os
from dotenv import load_dotenv
load_dotenv()

_raw = os.getenv("DATABASE_URL", "sqlite:///./storyteller.db")
# Render/Railway use postgres://; SQLAlchemy 2.x wants postgresql://
if _raw.startswith("postgres://"):
    _raw = _raw.replace("postgres://", "postgresql://", 1)
# Use pg8000 (pure Python) for PostgreSQL so no libpq.so is needed on Railway
if _raw.startswith("postgresql://") and "+" not in _raw.split("?")[0]:
    _raw = _raw.replace("postgresql://", "postgresql+pg8000://", 1)
DATABASE_URL = _raw

JUDGE_PROVIDER = os.getenv("JUDGE_PROVIDER", "").strip().lower()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
