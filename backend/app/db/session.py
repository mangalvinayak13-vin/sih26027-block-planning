import os

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

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
