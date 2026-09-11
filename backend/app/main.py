from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import router
from app.db.models import Base
from app.db.session import SessionLocal, engine
from app.seed import seed_if_empty

app = FastAPI(title="SIH26027 — AI-Powered Automatic Block Planning (Prototype)")

# The React dev server runs on a different port than this API, so the
# browser treats them as different "origins" and blocks requests unless
# we explicitly allow it. Wide open here because this is a local
# prototype, not something exposed on the internet.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)


def init_db():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        seed_if_empty(db)
    finally:
        db.close()


# Run this at IMPORT time, not only inside a FastAPI "startup" event.
# WHY: on Vercel, this whole module is re-imported fresh on every cold
# start of the serverless function — there's no long-running process for
# an ASGI "startup" lifespan event to reliably fire the same way it does
# under a normal uvicorn server. Import-time execution runs exactly once
# per cold start either way, so it works correctly in both environments.
init_db()


@app.get("/api/health")
def health():
    return {"status": "ok"}
