import os
from dotenv import load_dotenv

load_dotenv()

# ------------------- Основные настройки -------------------
BOT_TOKEN = os.getenv("BOT_TOKEN", "")
ADMIN_IDS = list(map(int, os.getenv("ADMIN_IDS", "0").split(",")))
DB_PATH = "bot_data.db"

# Telegram API credentials (Telegram Desktop fallback — works with any .session file)
API_ID = int(os.getenv("API_ID", "2040"))
API_HASH = os.getenv("API_HASH", "b18441a1ff607e10a989891a5462e627")

SESSIONS_DIR = "sessions"

# ------------------- Настройки для деплоя (Railway / VPS) -------------------
HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", os.getenv("API_PORT", "8080")))

# ------------------- API URL (публичный эндпоинт) -------------------
_custom_url = os.getenv("API_BASE_URL", "")
_railway_domain = os.getenv("RAILWAY_PUBLIC_DOMAIN", "")
_replit_domain = os.getenv("REPLIT_DEV_DOMAIN", "")

if _custom_url:
    API_BASE_URL = _custom_url.rstrip("/")
elif _railway_domain:
    API_BASE_URL = f"https://{_railway_domain}/api/v1"
elif _replit_domain:
    API_BASE_URL = f"https://{_replit_domain}/api/v1"
else:
    API_BASE_URL = f"http://{HOST}:{PORT}/api/v1"

# ------------------- Кеширование -------------------
USERNAME_CACHE_TTL = 3600

# ------------------- Лимиты на проверки -------------------
FREE_DAILY_ATTEMPTS = 3
PREMIUM_DAILY_ATTEMPTS = 999999
LUXE_DAILY_ATTEMPTS = 999999

BULK_PREMIUM_PER_DAY = 15   # ✅ изменено с 10 на 15
BULK_LUXE_PER_DAY = 100
BULK_SIZE = 5

# ------------------- Мультипоточность (пул сессий) -------------------
MAX_SESSIONS = int(os.getenv("MAX_SESSIONS", 10))
MAX_CONCURRENT_CHECKS = int(os.getenv("MAX_CONCURRENT_CHECKS", 15))   # <--- ДОБАВЛЕНО

# ------------------- Цены на подписки (в Stars) -------------------
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

# ------------------- Реферальная система -------------------
DEFAULT_REFERRAL_REWARDS = {
    "7": 1, "14": 3, "25": 10, "50": 25,
}

DEFAULT_BULK_EXTRA_PRICE = {"stars": 50}
