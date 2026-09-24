import os
from dotenv import load_dotenv

load_dotenv()

WATCHED_CHANNELS = [1522742073516622028, 1522742073516622029]
TARGET_EMOJI = "🔔"  
DB_FILE = "reminders.json"

BOT_TOKEN = os.getenv("BOT_TOKEN")

if not BOT_TOKEN:
    raise ValueError("CRITICAL: BOT_TOKEN is missing from your .env file!")

COOLDOWNS = {}
PROCESSING_REACTIONS = set()
