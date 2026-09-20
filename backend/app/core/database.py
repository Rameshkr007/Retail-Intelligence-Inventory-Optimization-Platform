"""
Database engine. Uses DATABASE_URL from settings (PostgreSQL in production —
see docker-compose.yml). Falls back to a local SQLite file when no Postgres
is reachable, so the app is runnable out of the box for demos/dev without
provisioning a server. This fallback is explicit, not silent: it's only used
when RETAIL_DB_FALLBACK_SQLITE=1 or when settings.database_url points at
sqlite.
"""
from __future__ import annotations

import os

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import settings


def _resolve_database_url() -> str:
    url = os.environ.get("DATABASE_URL", settings.database_url)
    if os.environ.get("RETAIL_DB_FALLBACK_SQLITE") == "1":
        return "sqlite:///./retail_intelligence.db"
    return url


DATABASE_URL = _resolve_database_url()
connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(DATABASE_URL, connect_args=connect_args)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


class Base(DeclarativeBase):
    pass


def get_db():
    db: Session = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    from app.models import orm  # noqa: F401  (ensures models are registered)
    Base.metadata.create_all(bind=engine)
