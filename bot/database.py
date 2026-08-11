import aiosqlite
import json
import secrets
from datetime import datetime, date
from bot.config import DB_PATH, DEFAULT_PREMIUM_PRICES, DEFAULT_REFERRAL_REWARDS, DEFAULT_LUXE_PRICES, DEFAULT_BULK_EXTRA_PRICE

async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                premium_until TEXT,
                luxe_until TEXT,
                referrer_id INTEGER,
                referral_count INTEGER DEFAULT 0,
                total_searches INTEGER DEFAULT 0,
                found_count INTEGER DEFAULT 0,
                today_searches INTEGER DEFAULT 0,
                last_search_date TEXT,
                bulk_today INTEGER DEFAULT 0,
                bulk_date TEXT,
                bulk_extra INTEGER DEFAULT 0,
                api_key TEXT UNIQUE,
                registered_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        # Добавляем новые колонки для улучшенной статистики
        cols_to_add = [
            ("luxe_until", "TEXT"),
            ("bulk_today", "INTEGER DEFAULT 0"),
            ("bulk_date", "TEXT"),
            ("bulk_extra", "INTEGER DEFAULT 0"),
            ("api_key", "TEXT"),
            ("avg_rating", "REAL DEFAULT 0.0"),          # новая
            ("last_active", "TEXT"),                     # новая
        ]
        for col, col_type in cols_to_add:
            try:
                await db.execute(f"ALTER TABLE users ADD COLUMN {col} {col_type}")
            except Exception:
                pass

        await db.execute("""
            CREATE TABLE IF NOT EXISTS found_usernames (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                username TEXT,
                length INTEGER,
                rating INTEGER,
                found_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS traps (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                target_username TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                notified INTEGER DEFAULT 0,
                check_interval INTEGER DEFAULT 1800,
                last_checked_at TEXT
            )
        """)
        trap_cols = [
            ("check_interval", "INTEGER DEFAULT 1800"),
            ("last_checked_at", "TEXT"),
        ]
        for col, col_type in trap_cols:
            try:
                await db.execute(f"ALTER TABLE traps ADD COLUMN {col} {col_type}")
            except Exception:
                pass

        await db.execute("""
            CREATE TABLE IF NOT EXISTS promo_codes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                code TEXT UNIQUE,
                days INTEGER,
                sub_type TEXT DEFAULT 'premium',
                max_uses INTEGER,
                used_count INTEGER DEFAULT 0,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS promo_uses (
                user_id INTEGER,
                code TEXT,
                PRIMARY KEY (user_id, code)
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS registered_channels (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                channel_id INTEGER,
                channel_username TEXT,
                channel_title TEXT,
                account_phone TEXT,
                account_username TEXT,
                registered_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        await db.execute("""
            INSERT OR IGNORE INTO settings (key, value) VALUES
                ('premium_prices', ?),
                ('luxe_prices', ?),
                ('referral_rewards', ?),
                ('bulk_extra_price', ?)
        """, (
            json.dumps(DEFAULT_PREMIUM_PRICES),
            json.dumps(DEFAULT_LUXE_PRICES),
            json.dumps(DEFAULT_REFERRAL_REWARDS),
            json.dumps(DEFAULT_BULK_EXTRA_PRICE),
        ))
        await db.commit()


async def get_user(user_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)) as cur:
            return await cur.fetchone()


async def get_user_by_api_key(api_key: str):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM users WHERE api_key = ?", (api_key,)) as cur:
            return await cur.fetchone()


async def create_user(user_id: int, username: str, referrer_id: int = None):
    async with aiosqlite.connect(DB_PATH) as db:
        today = date.today().isoformat()
        await db.execute("""
            INSERT OR IGNORE INTO users
                (user_id, username, referrer_id, last_search_date, bulk_date, registered_at)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (user_id, username, referrer_id, today, today, datetime.now().isoformat()))
        await db.commit()


async def update_username(user_id: int, username: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE users SET username=? WHERE user_id=?", (username, user_id))
        await db.commit()


# ─── Subscription helpers ───────────────────────────────────────────────────

def _sub_until(row, field: str):
    if not row or not row[field]:
        return None
    try:
        dt = datetime.fromisoformat(row[field])
        return dt if dt > datetime.now() else None
    except Exception:
        return None


async def is_premium(user_id: int) -> bool:
    user = await get_user(user_id)
    return bool(_sub_until(user, "premium_until") or _sub_until(user, "luxe_until"))


async def is_luxe(user_id: int) -> bool:
    user = await get_user(user_id)
    return bool(_sub_until(user, "luxe_until"))


async def get_premium_until(user_id: int):
    user = await get_user(user_id)
    return _sub_until(user, "premium_until") or _sub_until(user, "luxe_until")


async def get_luxe_until(user_id: int):
    user = await get_user(user_id)
    return _sub_until(user, "luxe_until")


async def add_premium_days(user_id: int, days: int, sub_type: str = "premium"):
    from datetime import timedelta
    field = "luxe_until" if sub_type == "luxe" else "premium_until"
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(f"SELECT {field} FROM users WHERE user_id=?", (user_id,)) as cur:
            row = await cur.fetchone()
        now = datetime.now()
        base = now
        if row and row[field]:
            try:
                cur_dt = datetime.fromisoformat(row[field])
                if cur_dt > now:
                    base = cur_dt
            except Exception:
                pass
        new_until = (base + timedelta(days=days)).isoformat()
        await db.execute(f"UPDATE users SET {field}=? WHERE user_id=?", (new_until, user_id))
        await db.commit()


async def revoke_premium(user_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE users SET premium_until=NULL, luxe_until=NULL WHERE user_id=?",
            (user_id,)
        )
        await db.commit()


# ─── Searches ───────────────────────────────────────────────────────────────

async def get_today_searches(user_id: int) -> int:
    user = await get_user(user_id)
    if not user:
        return 0
    if user["last_search_date"] != date.today().isoformat():
        return 0
    return user["today_searches"] or 0


async def increment_search(user_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        today = date.today().isoformat()
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT last_search_date, today_searches FROM users WHERE user_id=?", (user_id,)
        ) as cur:
            row = await cur.fetchone()
        today_count = 1 if row["last_search_date"] != today else (row["today_searches"] or 0) + 1
        await db.execute("""
            UPDATE users SET total_searches=total_searches+1,
                today_searches=?, last_search_date=?
            WHERE user_id=?
        """, (today_count, today, user_id))
        await db.commit()


async def increment_found(user_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE users SET found_count=found_count+1 WHERE user_id=?", (user_id,))
        await db.commit()


# ─── Bulk search ────────────────────────────────────────────────────────────

async def get_bulk_used_today(user_id: int) -> int:
    user = await get_user(user_id)
    if not user:
        return 0
    if user["bulk_date"] != date.today().isoformat():
        return 0
    return user["bulk_today"] or 0


async def get_bulk_extra(user_id: int) -> int:
    user = await get_user(user_id)
    return user["bulk_extra"] or 0 if user else 0


async def increment_bulk(user_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        today = date.today().isoformat()
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT bulk_date, bulk_today, bulk_extra FROM users WHERE user_id=?", (user_id,)
        ) as cur:
            row = await cur.fetchone()
        if row["bulk_date"] != today:
            today_count = 1
        else:
            today_count = (row["bulk_today"] or 0) + 1
        await db.execute("""
            UPDATE users SET bulk_today=?, bulk_date=? WHERE user_id=?
        """, (today_count, today, user_id))
        await db.commit()


async def add_bulk_extra(user_id: int, amount: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE users SET bulk_extra=bulk_extra+? WHERE user_id=?", (amount, user_id)
        )
        await db.commit()


async def spend_bulk_extra(user_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE users SET bulk_extra=MAX(0, bulk_extra-1) WHERE user_id=?", (user_id,)
        )
        await db.commit()


# ─── Found usernames / history ──────────────────────────────────────────────

async def save_found_username(user_id: int, username: str, length: int, rating: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT INTO found_usernames (user_id, username, length, rating)
            VALUES (?, ?, ?, ?)
        """, (user_id, username, length, rating))
        await db.commit()


async def get_last_found(user_id: int, limit: int = 100):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("""
            SELECT * FROM found_usernames WHERE user_id=?
            ORDER BY found_at DESC LIMIT ?
        """, (user_id, limit)) as cur:
            return await cur.fetchall()


# ─── Traps ──────────────────────────────────────────────────────────────────

async def add_trap(user_id: int, target_username: str, check_interval: int = 1800):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT OR REPLACE INTO traps (user_id, target_username, notified, check_interval)
            VALUES (?, ?, 0, ?)
        """, (user_id, target_username.lower(), check_interval))
        await db.commit()


async def update_trap_interval(trap_id: int, check_interval: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE traps SET check_interval=? WHERE id=?", (check_interval, trap_id)
        )
        await db.commit()


async def update_trap_last_checked(trap_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE traps SET last_checked_at=? WHERE id=?",
            (datetime.now().isoformat(), trap_id)
        )
        await db.commit()


async def get_user_traps(user_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM traps WHERE user_id=? AND notified=0", (user_id,)
        ) as cur:
            return await cur.fetchall()


async def get_all_active_traps():
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM traps WHERE notified=0") as cur:
            return await cur.fetchall()


async def mark_trap_notified(trap_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE traps SET notified=1 WHERE id=?", (trap_id,))
        await db.commit()


async def delete_trap(trap_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM traps WHERE id=?", (trap_id,))
        await db.commit()


# ─── Referrals ──────────────────────────────────────────────────────────────

async def get_referral_count(user_id: int) -> int:
    user = await get_user(user_id)
    return user["referral_count"] if user else 0


async def add_referral(referrer_id: int) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE users SET referral_count=referral_count+1 WHERE user_id=?", (referrer_id,)
        )
        await db.commit()
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT referral_count FROM users WHERE user_id=?", (referrer_id,)) as cur:
            row = await cur.fetchone()
        return row["referral_count"] if row else 0


# ─── Settings ───────────────────────────────────────────────────────────────

async def get_setting(key: str):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT value FROM settings WHERE key=?", (key,)) as cur:
            row = await cur.fetchone()
        return json.loads(row[0]) if row else None


async def set_setting(key: str, value):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
            (key, json.dumps(value))
        )
        await db.commit()


# ─── Promo codes ────────────────────────────────────────────────────────────

async def create_promo(code: str, days: int, max_uses: int, sub_type: str = "premium"):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT INTO promo_codes (code, days, max_uses, sub_type)
            VALUES (?, ?, ?, ?)
        """, (code.upper(), days, max_uses, sub_type))
        await db.commit()


async def use_promo(user_id: int, code: str):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM promo_codes WHERE code=?", (code.upper(),)
        ) as cur:
            promo = await cur.fetchone()
        if not promo:
            return None, None, "not_found"
        if promo["used_count"] >= promo["max_uses"]:
            return None, None, "expired"
        async with db.execute(
            "SELECT 1 FROM promo_uses WHERE user_id=? AND code=?", (user_id, code.upper())
        ) as cur:
            if await cur.fetchone():
                return None, None, "already_used"
        await db.execute(
            "UPDATE promo_codes SET used_count=used_count+1 WHERE code=?", (code.upper(),)
        )
        await db.execute("INSERT INTO promo_uses (user_id, code) VALUES (?, ?)", (user_id, code.upper()))
        await db.commit()
        return promo["days"], promo["sub_type"], "ok"


# ─── API keys ───────────────────────────────────────────────────────────────

async def generate_api_key(user_id: int) -> str:
    key = "luxe_" + secrets.token_hex(20)
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE users SET api_key=? WHERE user_id=?", (key, user_id))
        await db.commit()
    return key


async def get_api_key(user_id: int) -> str | None:
    user = await get_user(user_id)
    return user["api_key"] if user else None


# ─── Registered channels ────────────────────────────────────────────────────

async def add_registered_channel(channel_id: int, channel_username: str, channel_title: str,
                                  account_phone: str, account_username: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT OR REPLACE INTO registered_channels
                (channel_id, channel_username, channel_title, account_phone, account_username)
            VALUES (?, ?, ?, ?, ?)
        """, (channel_id, channel_username, channel_title, account_phone, account_username))
        await db.commit()


async def get_registered_channels():
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM registered_channels ORDER BY registered_at DESC"
        ) as cur:
            return await cur.fetchall()


async def get_registered_channel(channel_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM registered_channels WHERE channel_id=?", (channel_id,)
        ) as cur:
            return await cur.fetchone()


async def delete_registered_channel(channel_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM registered_channels WHERE channel_id=?", (channel_id,))
        await db.commit()


async def update_registered_channel_username(channel_id: int, new_username: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE registered_channels SET channel_username=? WHERE channel_id=?",
            (new_username, channel_id)
        )
        await db.commit()


# ─── Admin helpers ──────────────────────────────────────────────────────────

async def get_all_users():
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM users") as cur:
            return await cur.fetchall()


async def get_all_promos():
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM promo_codes ORDER BY created_at DESC") as cur:
            return await cur.fetchall()


async def find_user_by_identifier(identifier: str):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        identifier = identifier.strip().lstrip("@")
        if identifier.isdigit():
            async with db.execute("SELECT * FROM users WHERE user_id=?", (int(identifier),)) as cur:
                return await cur.fetchone()
        else:
            async with db.execute(
                "SELECT * FROM users WHERE username=?", (identifier,)
            ) as cur:
                return await cur.fetchone()


# ════════════════════════════════════════════════════════════════════════════════
#  НОВЫЕ ФУНКЦИИ ДЛЯ УЛУЧШЕННОЙ СТАТИСТИКИ
# ════════════════════════════════════════════════════════════════════════════════

async def update_user_stats(user_id: int, searched: int = 1, found: int = 0, rating: float = 0.0):
    """
    Обновляет статистику пользователя после каждой проверки.
    - searched: количество проверенных юзернеймов (обычно 1)
    - found: количество найденных свободных (0 или 1)
    - rating: рейтинг найденного ника (если found=1)
    """
    async with aiosqlite.connect(DB_PATH) as db:
        now = datetime.now().isoformat()
        today = date.today().isoformat()

        # Проверяем, нужно ли обнулить today_searches
        await db.execute("""
            UPDATE users 
            SET today_searches = 0, today_found = 0, bulk_today = 0
            WHERE user_id = ? AND (last_search_date IS NULL OR last_search_date < ?)
        """, (user_id, today))

        # Обновляем основные счётчики
        # Если found=1, то увеличиваем found_count и обновляем avg_rating
        if found > 0:
            await db.execute("""
                INSERT INTO users (user_id, total_searches, found_count, today_searches, today_found, avg_rating, last_active)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(user_id) DO UPDATE SET
                    total_searches = total_searches + excluded.total_searches,
                    found_count = found_count + excluded.found_count,
                    today_searches = today_searches + excluded.today_searches,
                    today_found = CASE 
                        WHEN last_search_date = ? THEN today_found + 1 
                        ELSE 1 
                    END,
                    avg_rating = CASE 
                        WHEN found_count = 0 THEN ? 
                        ELSE (avg_rating * found_count + ?) / (found_count + 1) 
                    END,
                    last_active = excluded.last_active,
                    last_search_date = ?
            """, (user_id, searched, found, searched, rating, today, rating, rating, today))
        else:
            # только поиск без находки
            await db.execute("""
                INSERT INTO users (user_id, total_searches, today_searches, last_active, last_search_date)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(user_id) DO UPDATE SET
                    total_searches = total_searches + excluded.total_searches,
                    today_searches = CASE 
                        WHEN last_search_date = ? THEN today_searches + 1 
                        ELSE 1 
                    END,
                    last_active = excluded.last_active,
                    last_search_date = excluded.last_search_date
            """, (user_id, searched, searched, now, today, today))

        await db.commit()


async def get_user_stats(user_id: int) -> dict:
    """
    Возвращает словарь со всей статистикой пользователя:
        - premium_until, luxe_until, referrals
        - total_searches, total_found, today_searches, today_found
        - avg_rating, last_active
    """
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("""
            SELECT premium_until, luxe_until, referral_count, 
                   total_searches, found_count, 
                   today_searches, 
                   COALESCE((SELECT SUM(found_count) FROM users WHERE user_id = ? AND last_search_date = date('now')), 0) AS today_found,
                   avg_rating, last_active
            FROM users WHERE user_id = ?
        """, (user_id, user_id)) as cur:
            row = await cur.fetchone()
        if not row:
            return {
                "premium_until": None,
                "luxe_until": None,
                "referrals": 0,
                "total_searches": 0,
                "total_found": 0,
                "today_searches": 0,
                "today_found": 0,
                "avg_rating": 0.0,
                "last_active": None
            }
        return {
            "premium_until": row["premium_until"],
            "luxe_until": row["luxe_until"],
            "referrals": row["referral_count"] or 0,
            "total_searches": row["total_searches"] or 0,
            "total_found": row["found_count"] or 0,
            "today_searches": row["today_searches"] or 0,
            "today_found": row["today_found"] or 0,
            "avg_rating": row["avg_rating"] or 0.0,
            "last_active": row["last_active"]
        }
