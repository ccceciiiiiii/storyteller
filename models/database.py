"""Database engine and session - SQLite/PostgreSQL compatible."""
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool

from config import DATABASE_URL
from .tables import Base

# SQLite needs check_same_thread=False for FastAPI; use StaticPool for :memory: or file
connect_args = {}
if DATABASE_URL.startswith("sqlite"):
    connect_args["check_same_thread"] = False
    # Optional: use StaticPool only for :memory:
    # engine = create_engine(DATABASE_URL, connect_args=connect_args, poolclass=StaticPool)
engine = create_engine(
    DATABASE_URL,
    connect_args=connect_args,
    echo=False,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_session() -> Session:
    return SessionLocal()


def init_db():
    Base.metadata.create_all(bind=engine)
    # Add min_participants_to_start if missing (existing DBs)
    with engine.connect() as conn:
        try:
            if DATABASE_URL.startswith("sqlite"):
                conn.execute(text("ALTER TABLE stories ADD COLUMN min_participants_to_start INTEGER NOT NULL DEFAULT 2"))
            else:
                conn.execute(text("ALTER TABLE stories ADD COLUMN IF NOT EXISTS min_participants_to_start INTEGER NOT NULL DEFAULT 2"))
            conn.commit()
        except Exception:
            conn.rollback()
            # Column may already exist
            pass
