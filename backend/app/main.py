"""The FastAPI application.

Run it with, from backend/:
    .venv/Scripts/python.exe -m uvicorn app.main:app --reload --port 8000
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .core.config import CORS_ORIGINS
from .features.auth import router as auth
from .features.classes import router as classes
from .features.funds import router as funds
from .features.trading import router as students

app = FastAPI(
    title="AI Classroom",
    description="A classroom investing simulator. Virtual money, real mutual funds.",
    version="1.0.0",
)

# The frontend is served from a different port in development and a different
# domain in production, so the browser treats it as a different origin and blocks
# the calls unless the server says otherwise. That is what this does.
#
# Locally, Vite's port drifts (5173, 5174, ... on dev; 4173 on `npm run preview`)
# depending on what else is already running, and it is easy to lose track of
# which one is live. allow_origin_regex covers any localhost/127.0.0.1 port so
# that drift stops being a recurring CORS error -- it is still limited to the
# developer's own machine, never a wildcard on real origins. CORS_ORIGINS
# remains the explicit allowlist for the deployed frontend in production.
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_origin_regex=r"^http://(localhost|127\.0\.0\.1):\d+$",
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(funds.router)
app.include_router(students.router)
app.include_router(classes.router)


@app.get("/api/health")
def health():
    """Somewhere to point a deploy platform's health check."""
    return {"status": "ok"}
