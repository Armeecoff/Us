"""
UqozaSearch — демо-скрипт поиска юзернеймов через Telegram API (Telethon).

Использование:
    pip install telethon httpx
    python username_search_demo.py

Переменные окружения (или вписать напрямую):
    API_ID   — из my.telegram.org
    API_HASH — из my.telegram.org
    PHONE    — ваш номер телефона
"""

import asyncio
import os
import random
import string
import httpx
from telethon import TelegramClient
from telethon.tl.functions.contacts import ResolveUsernameRequest
from telethon.errors import UsernameNotOccupiedError, UsernameInvalidError, FloodWaitError

# ─── Настройки ────────────────────────────────────────────────────────────────
API_ID   = int(os.getenv("API_ID", "2040"))
API_HASH = os.getenv("API_HASH", "b18441a1ff607e10a989891a5462e627")
PHONE    = os.getenv("PHONE", "+79991234567")  # замените на ваш номер

SESSION_FILE = "demo_session"  # .session будет создан автоматически

# Параметры поиска
SEARCH_LENGTH  = 6      # длина ника (5 или 6)
WITH_DIGITS    = False  # включать цифры
NEED_COUNT     = 5      # сколько свободных ников найти
MAX_ATTEMPTS   = 500    # максимум проверок


# ─── Генерация и оценка ──────────────────────────────────────────────────────

def generate_username(length: int, with_digits: bool = False) -> str:
    letters = string.ascii_lowercase
    charset = letters + (string.digits if with_digits else "")
    return random.choice(letters) + "".join(random.choices(charset, k=length - 1))


def rate_username(username: str) -> int:
    u = username.lower()
    score = 10
    if any(c.isdigit() for c in u):
        score -= 2
    if any(u[i] == u[i + 1] for i in range(len(u) - 1)):
        score -= 1
    if len(set(u)) < len(u) * 0.6:
        score -= 1
    vowels = sum(1 for c in u if c in "aeiou")
    if len(u) > 0 and ((vowels / len(u)) < 0.15 or (vowels / len(u)) > 0.7):
        score -= 1
    return max(1, min(10, score))


# ─── Проверка через Fragment ──────────────────────────────────────────────────

async def check_fragment(username: str) -> bool:
    """True = ник НЕ на аукционе (безопасен), False = выставлен на Fragment."""
    try:
        async with httpx.AsyncClient(follow_redirects=False, timeout=4.0,
                                      headers={"User-Agent": "Mozilla/5.0"}) as c:
            r = await c.get(f"https://fragment.com/username/{username}")
        if r.status_code == 302:
            return True
        if r.status_code == 200:
            t = r.text.lower()
            return not any(s in t for s in ["place a bid", "buy now", "last bid", "min bid", "auction"])
        return True
    except Exception:
        return True


# ─── Основной поиск ──────────────────────────────────────────────────────────

async def find_free_usernames(client: TelegramClient) -> list[dict]:
    found = []
    attempts = 0
    seen = set()

    print(f"\n🔍 Ищу {NEED_COUNT} свободных ника длиной {SEARCH_LENGTH}...\n")

    while len(found) < NEED_COUNT and attempts < MAX_ATTEMPTS:
        username = generate_username(SEARCH_LENGTH, WITH_DIGITS)
        if username in seen:
            continue
        seen.add(username)
        attempts += 1

        try:
            # 1. Проверяем через Telethon
            try:
                await client(ResolveUsernameRequest(username))
                print(f"  ✗ @{username} — занят")
                continue
            except UsernameNotOccupiedError:
                pass  # свободен в Telegram
            except UsernameInvalidError:
                continue
            except FloodWaitError as e:
                print(f"  ⏳ FloodWait {e.seconds}s...")
                await asyncio.sleep(min(e.seconds, 5))
                continue

            # 2. Проверяем через Fragment
            safe = await check_fragment(username)
            if not safe:
                print(f"  ✗ @{username} — на аукционе Fragment")
                continue

            # 3. Оцениваем и добавляем
            rating = rate_username(username)
            stars = "⭐" * rating + "☆" * (10 - rating)
            print(f"  ✅ @{username} [{rating}/10] {stars}")
            found.append({
                "username": username,
                "rating": rating,
                "link": f"https://t.me/{username}"
            })

        except Exception as e:
            print(f"  ⚠️  Ошибка при проверке @{username}: {e}")

        await asyncio.sleep(0.3)  # небольшая задержка

    return found


# ─── Запуск ──────────────────────────────────────────────────────────────────

async def main():
    print("=" * 50)
    print("  UqozaSearch Demo — поиск юзернеймов")
    print("=" * 50)

    async with TelegramClient(SESSION_FILE, API_ID, API_HASH) as client:
        await client.start(phone=PHONE)
        me = await client.get_me()
        print(f"\n✅ Авторизован как: @{me.username or me.id}")

        results = await find_free_usernames(client)

        print(f"\n{'=' * 50}")
        print(f"🎉 Найдено: {len(results)} из {NEED_COUNT}")
        print("=" * 50)
        for r in results:
            print(f"  @{r['username']} — рейтинг {r['rating']}/10 — {r['link']}")
        print()


if __name__ == "__main__":
    asyncio.run(main())
