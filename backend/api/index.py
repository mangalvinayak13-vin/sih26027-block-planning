# Vercel's Python runtime turns any file under api/ that exposes an ASGI
# app (a variable named `app`) into a serverless function automatically —
# no extra adapter code needed. This file just re-exports the real
# FastAPI app from app/main.py so Vercel has something to find here.
from app.main import app  # noqa: F401
