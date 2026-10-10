import os
from pathlib import Path
from dotenv import load_dotenv

# Project root = the folder above Python/, wherever the project lives
BASE_DIR = Path(__file__).resolve().parent.parent
CACHE_DIR = BASE_DIR / "Local-Cache"
IMAGE_DIR = CACHE_DIR / "stored_images"
IMAGE_DIR.mkdir(parents=True, exist_ok=True)

load_dotenv(BASE_DIR / ".env")

WATCHED_CHANNELS = [1522742073516622028, 1522742073516622029]
TARGET_EMOJI = "🔔"  
DB_FILE = CACHE_DIR / "reminders.json"

BOT_TOKEN = os.getenv("BOT_TOKEN")

if not BOT_TOKEN:
    raise ValueError("CRITICAL: BOT_TOKEN is missing from your .env file!")

COOLDOWNS = {}
PROCESSING_REACTIONS = set()