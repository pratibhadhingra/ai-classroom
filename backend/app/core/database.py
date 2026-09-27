"""Database connection.

Postgres, hosted on Supabase. Two reasons it is not SQLite:

* The app is deployed, and free-tier hosts give you an ephemeral filesystem -- a
  SQLite file would be wiped on every restart and redeploy, so the live link
  would lose its data at random.
* Postgres has a real NUMERIC type, so money is stored exactly with no
  workaround. On SQLite, SQLAlchemy converts Decimal through float to store it.

The connection string lives in backend/.env, which is gitignored. See
.env.example for the shape of it.
"""

import os
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

load_dotenv(Path(__file__).resolve().parent.parent.parent / ".env")  # backend/.env

RAW_DATABASE_URL = os.getenv("DATABASE_URL")
if not RAW_DATABASE_URL:
    raise RuntimeError(
        "DATABASE_URL is not set. Copy backend/.env.example to backend/.env and "
        "paste your Supabase session-pooler connection string into it."
    )


def _normalise(url: str) -> str:
    """Point the URL at psycopg 3.

    Supabase hands you a URL starting `postgresql://`. SQLAlchemy reads that as
    "use psycopg2", which is not what we installed. Rewriting the prefix here
    means the string can be pasted from the dashboard unedited, instead of
    failing with a confusing driver error.
    """
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+psycopg://", 1)
    if url.startswith("postgres://"):
        return url.replace("postgres://", "postgresql+psycopg://", 1)
    return url


engine = create_engine(
    _normalise(RAW_DATABASE_URL),
    # Supabase closes idle connections, and a dead one in the pool surfaces as a
    # random failure on some later request. pre_ping spends one cheap round trip
    # checking a connection is alive before handing it out.
    pool_pre_ping=True,
    pool_size=5,
    max_overflow=5,
)

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


class Base(DeclarativeBase):
    """Parent class for every table. SQLAlchemy collects tables through it."""


def get_db():
    """Hand one database session to a request, and always close it afterwards.

    FastAPI calls this for any endpoint that declares `db: Session = Depends(get_db)`.
    The `yield` is what makes the closing happen even if the endpoint raises.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def create_tables() -> None:
    """Create any table that does not exist yet. Existing tables are untouched.

    The import is inside the function on purpose. SQLAlchemy only knows about a
    table once the class defining it has been imported, so calling this without
    having imported models first silently creates nothing. Importing here means
    it cannot be called wrongly. It sits inside the function rather than at the
    top of the file because models/__init__.py imports Base from here, and a
    top-level import would be circular.
    """
    from .. import models  # noqa: F401

    Base.metadata.create_all(bind=engine)
