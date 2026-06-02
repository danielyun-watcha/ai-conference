import os
from pathlib import Path

from dotenv import load_dotenv

BACKEND_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BACKEND_DIR.parent
CONFERENCES_DIR = PROJECT_ROOT / "src" / "data" / "conferences"
DB_PATH = BACKEND_DIR / "state.db"

# Load .env from backend/ first, fall back to project root
load_dotenv(BACKEND_DIR / ".env")
load_dotenv(PROJECT_ROOT / ".env")

SLACK_WEBHOOK_URL = os.getenv("SLACK_WEBHOOK_URL", "").strip()
HTTP_TIMEOUT = float(os.getenv("CRAWLER_HTTP_TIMEOUT", "15"))
USER_AGENT = os.getenv(
    "CRAWLER_USER_AGENT",
    "ai-deadlines-bot/0.1 (+https://github.com/daniel/ai-deadlines)",
)

# CORS origins for the frontend dev server and future deploys
CORS_ORIGINS = [
    o.strip()
    for o in os.getenv(
        "CORS_ORIGINS",
        "http://localhost:5002,http://127.0.0.1:5002",
    ).split(",")
    if o.strip()
]
