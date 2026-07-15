import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent  # job-agent/backend
load_dotenv(BASE_DIR / ".env")

STORAGE_DIR = Path(os.getenv("STORAGE_DIR", str(BASE_DIR / "storage")))
RESUME_DIR = STORAGE_DIR / "resumes"
SCREENSHOT_DIR = STORAGE_DIR / "screenshots"
DB_PATH = STORAGE_DIR / "app.db"

ANTHROPIC_MODEL = os.getenv("ANTHROPIC_MODEL", "claude-opus-4-8")
MAX_JOBS_PER_SCAN = int(os.getenv("MAX_JOBS_PER_SCAN", "25"))
HEADLESS = os.getenv("HEADLESS", "true").strip().lower() != "false"
FETCH_DELAY_SECONDS = float(os.getenv("FETCH_DELAY_SECONDS", "1.0"))

USER_AGENT = "JobApplicationAgent/0.1 (personal job-search assistant; contact: user)"

# Compliance: domains this agent refuses to scan or automate.
BLOCKED_DOMAINS = ("linkedin.com", "licdn.com")

for _d in (RESUME_DIR, SCREENSHOT_DIR):
    _d.mkdir(parents=True, exist_ok=True)
