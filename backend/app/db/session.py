import os

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# On Vercel, the deployed function's own directory is READ-ONLY — only
# /tmp is writable, and it's wiped on every cold start. That means on
# Vercel this database resets often (no durable approvals between
# requests); locally it's a normal persistent file. VERCEL is a env var
# Vercel sets automatically inside every deployed function, so we don't
# need any manual config to tell the two environments apart.
if os.environ.get("VERCEL"):
    DB_PATH = "/tmp/block_planning.db"
else:
    DB_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "data", "block_planning.db")
    DB_PATH = os.path.abspath(DB_PATH)

# check_same_thread=False is needed because FastAPI can hand requests to
# different worker threads, but a single SQLite connection object is only
# safe to use from one thread by default.
engine = create_engine(f"sqlite:///{DB_PATH}", connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
