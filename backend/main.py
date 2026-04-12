"""
RaceDB — FastAPI application entry point
"""
import sys
import os

# Make backend/ the module root so relative imports work
sys.path.insert(0, os.path.dirname(__file__))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from routers import debug, benchmark, logs

app = FastAPI(
    title="RaceDB — Real-Time Data Consistency Debugger",
    description=(
        "Transaction concurrency testing & benchmarking system for MySQL InnoDB. "
        "Supports deterministic debug scenarios and high-concurrency load testing."
    ),
    version="1.0.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
)

# ── CORS (Fix #12: restricted to localhost instead of wildcard) ───────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:8000",
        "http://127.0.0.1:8000",
        "http://localhost:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── API routers ───────────────────────────────────────────────────────────
app.include_router(debug.router)
app.include_router(benchmark.router)
app.include_router(logs.router)


@app.get("/health", tags=["System"])
async def health():
    """Health-check endpoint."""
    return {"status": "ok", "service": "RaceDB"}


# ── Static frontend ────────────────────────────────────────────────────────
_frontend = os.path.join(os.path.dirname(__file__), "..", "frontend")
if os.path.isdir(_frontend):
    app.mount("/", StaticFiles(directory=_frontend, html=True), name="frontend")
