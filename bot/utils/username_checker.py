import asyncio
import random
import string
import logging
from typing import Optional, List
import httpx

from telethon.errors import (
    UsernameNotOccupiedError,
    UsernameInvalidError,
    FloodWaitError,
)
from telethon.tl.functions.contacts import ResolveUsernameRequest
from telethon.tl.functions.users import GetFullUserRequest

from bot.config import MAX_CONCURRENT_CHECKS
from bot.utils.session_manager import get_client, has_sessions, session_count

logger = logging.getLogger(__name__)

_bot = None
_checked_cache: dict[str, bool] = {}

def set_bot(bot):
    global _bot
    _bot = bot

def get_cached(username: str) -> Optional[bool]:
    return _checked_cache.get(username.lower())

def set_cached(username: str, is_free: bool):
    _checked_cache[username.lower()] = is_free

def generate_username(length: int, with_digits: bool = False) -> str:
    letters = string.ascii_lowercase
    charset = letters + (string.digits if with_digits else "")
    return random.choice(letters) + "".join(random.choices(charset, k=length - 1))

def rate_username(username: str) -> int:
    u = username.lower()
    score = 10
    if any(c.isdigit() for c in u):
        score -= 2
    if any(u[i] == u[i+1] for i in range(len(u)-1)):
        score -= 1
    if len(set(u)) < len(u) * 0.6:
        score -= 1
    vowels = sum(1 for c in u if c in "aeiou")
    if (vowels / len(u)) < 0.15 or (vowels / len(u)) > 0.7:
        score -= 1
    return max(1, min(10, score))

def apply_mask(mask: str) -> str:
    return "".join(
        random.choice(string.ascii_lowercase) if c == "?" else c.lower()
        for c in mask
    )

def validate_mask(mask: str) -> bool:
    if not mask or not (5 <= len(mask) <= 32):
        return False
    if not all(c in set(string.ascii_letters + string.digits + "?_") for c in mask):
        return False
    return mask[0].isalpha() or mask[0] == "?"

# ------------------- Проверки -------------------
async def check_telegram_telethon(username: str) -> Optional[bool]:
    """True = свободно, False = занято, None = ошибка"""
    if not has_sessions():
        return None
    client = await get_client()
    if not client:
        return None
    try:
        await client(ResolveUsernameRequest(username))
        # Если не упало – имя занято, уточняем статус
        full = await client(GetFullUserRequest(username))
        user = full.user
        if user:
            if user.bot or user.deleted:
                return False   # бот или удалёнка – не подходит
            return False       # обычный пользователь – занят
        return False           # канал/группа – тоже занято
    except UsernameNotOccupiedError:
        return True
    except UsernameInvalidError:
        return None
    except FloodWaitError as e:
        logger.warning(f"FloodWait {e.seconds}с для @{username}")
        await asyncio.sleep(min(e.seconds, 3))
        return None
    except Exception as e:
        logger.debug(f"Telethon ошибка @{username}: {e}")
        return None

async def check_telegram_bot_api(username: str) -> Optional[bool]:
    if not _bot:
        return None
    try:
        await _bot.get_chat(f"@{username}")
        return False
    except Exception as e:
        err = str(e).lower()
        if any(x in err for x in ("chat not found", "username not occupied", "not found", "username_not_occupied")):
            return True
        return None

async def check_telegram_http(username: str) -> Optional[bool]:
    try:
        async with httpx.AsyncClient(follow_redirects=True, timeout=5.0,
                                     headers={"User-Agent": "Mozilla/5.0"}) as c:
            r = await c.get(f"https://t.me/{username}")
        if r.status_code == 404:
            return True
        text = r.text
        taken = ['class="tgme_page_title"', 'class="tgme_page_photo"',
                 "tgme_page_photo_image", "tgme_page_description"]
        return False if any(s in text for s in taken) else True
    except Exception:
        return None

async def check_fragment(username: str) -> bool:
    """True = безопасно (не на Fragment), False = выставлен на продажу"""
    try:
        async with httpx.AsyncClient(follow_redirects=False, timeout=4.0,
                                     headers={"User-Agent": "Mozilla/5.0"}) as c:
            r = await c.get(f"https://fragment.com/username/{username}")
        if r.status_code == 302:
            return True
        if r.status_code != 200:
            return True
        text = r.text.lower()
        auction_indicators = [
            "place a bid", "buy now", "last bid", "min bid", "auction",
            "current bid", "starting bid", "reserve price", "bid now", "make offer"
        ]
        if any(ind in text for ind in auction_indicators):
            return False
        if 'class="button"' in text and ('bid' in text or 'buy' in text):
            if "₽" in text or "$" in text or "€" in text:
                return False
        return True
    except Exception:
        return True

async def is_username_free(username: str) -> bool:
    username = username.lower()
    cached = get_cached(username)
    if cached is not None:
        return cached

    tg = await check_telegram_telethon(username)
    if tg is False:
        set_cached(username, False)
        return False
    if tg is None:
        tg = await check_telegram_bot_api(username)
        if tg is False:
            set_cached(username, False)
            return False
        if tg is None:
            tg = await check_telegram_http(username)
            if tg is False:
                set_cached(username, False)
                return False
            if tg is None:
                # неопределённо – считаем занятым, чтобы не рисковать
                set_cached(username, False)
                return False

    # Теперь tg должен быть True (свободно)
    frag = await check_fragment(username)
    if frag is False:
        set_cached(username, False)
        return False

    set_cached(username, True)
    return True

# ------------------- Массовый поиск с мультипоточностью -------------------
async def find_free_usernames(
    length: int,
    with_digits: bool = False,
    mask: Optional[str] = None,
    min_rating: int = 1,
    count: int = 1,
    max_attempts: int = 800,
) -> list[tuple[str, int]]:
    # Определяем степень параллелизма на основе количества сессий
    sess_cnt = session_count() if has_sessions() else 0
    concurrency = min(MAX_CONCURRENT_CHECKS, max(5, sess_cnt * 3)) if sess_cnt else 5
    logger.debug(f"Concurrency: {concurrency}")

    seen = set()
    candidates = []
    for _ in range(max_attempts):
        uname = apply_mask(mask) if mask else generate_username(length, with_digits)
        if uname in seen or get_cached(uname) is False:
            continue
        seen.add(uname)
        rating = rate_username(uname)
        if rating >= min_rating:
            candidates.append((uname, rating))

    sem = asyncio.Semaphore(concurrency)
    results = []
    done_event = asyncio.Event()

    async def check_one(uname: str, rating: int):
        if done_event.is_set() and len(results) >= count:
            return
        async with sem:
            if done_event.is_set() and len(results) >= count:
                return
            if await is_username_free(uname):
                results.append((uname, rating))
                if len(results) >= count:
                    done_event.set()

    batch = 30
    for i in range(0, len(candidates), batch):
        if len(results) >= count:
            break
        await asyncio.gather(*[check_one(u, r) for u, r in candidates[i:i+batch]])

    return results[:count]

async def find_free_username(
    length: int,
    with_digits: bool = False,
    mask: Optional[str] = None,
    min_rating: int = 1,
    max_attempts: int = 800,
) -> Optional[tuple[str, int]]:
    found = await find_free_usernames(length, with_digits, mask, min_rating, count=1, max_attempts=max_attempts)
    return found[0] if found else None
