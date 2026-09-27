"""Settings read from the environment.

Only two things are configurable, and both differ between a laptop and a deployed
server. Everything else is a constant and lives next to the code that uses it.
"""

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent.parent / ".env")  # backend/.env

# Where the frontend is allowed to call from. 5173 is Vite's default dev port;
# 5174 is included too because Vite silently bumps to the next free port
# whenever something else is already holding 5173, which is easy to miss.
# In production set CORS_ORIGINS to the deployed frontend URL, comma separated.
DEFAULT_ORIGINS = (
    "http://localhost:5173,http://127.0.0.1:5173,"
    "http://localhost:5174,http://127.0.0.1:5174,"
    "http://localhost:3000"
)

CORS_ORIGINS = [
    origin.strip()
    for origin in os.getenv("CORS_ORIGINS", DEFAULT_ORIGINS).split(",")
    if origin.strip()
]
