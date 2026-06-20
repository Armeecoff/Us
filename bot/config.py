import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN", "")
ADMIN_IDS = list(map(int, os.getenv("ADMIN_IDS", "0").split(",")))
DB_PATH = "bot_data.db"

# Telegram API credentials (Telegram Desktop fallback — works with any .session file)
API_ID = int(os.getenv("API_ID", "2040"))
API_HASH = os.getenv("API_HASH", "b18441a1ff607e10a989891a5462e627")

SESSIONS_DIR = "sessions"
API_PORT = int(os.getenv("API_PORT", "8080"))

# Публичный URL API — задаётся вручную (Railway/VPS) или берётся из Replit
_replit_domain = os.getenv("REPLIT_DEV_DOMAIN", "")
_custom_url = os.getenv("API_BASE_URL", "")
if _custom_url:
    API_BASE_URL = _custom_url.rstrip("/")
elif _replit_domain:
    API_BASE_URL = f"https://{_replit_domain}/api/v1"
else:
    API_BASE_URL = f"http://localhost:{os.getenv('API_PORT', '8080')}/api/v1"

USERNAME_CACHE_TTL = 3600

FREE_DAILY_ATTEMPTS = 3
PREMIUM_DAILY_ATTEMPTS = 999999
LUXE_DAILY_ATTEMPTS = 999999

BULK_PREMIUM_PER_DAY = 10
BULK_LUXE_PER_DAY = 100
BULK_SIZE = 5

DEFAULT_PREMIUM_PRICES = {
    "1":  {"stars": 65},
    "3":  {"stars": 150},
    "10": {"stars": 400},
    "30": {"stars": 800},
}

DEFAULT_LUXE_PRICES = {
    "1":  {"stars": 120},
    "3":  {"stars": 280},
    "10": {"stars": 700},
    "30": {"stars": 1500},
}

DEFAULT_REFERRAL_REWARDS = {
    "7": 1, "14": 3, "25": 10, "50": 25,
}

DEFAULT_BULK_EXTRA_PRICE = {"stars": 50}
