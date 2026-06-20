import os
import asyncio
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

_clients: list = []
_client_index = 0
_lock = asyncio.Lock()
_pending_login: dict = {}  # phone -> {client, hash, path}


async def load_sessions(api_id: int, api_hash: str, sessions_dir: str = "sessions"):
    global _clients
    from telethon import TelegramClient

    os.makedirs(sessions_dir, exist_ok=True)
    session_files = list(Path(sessions_dir).glob("*.session"))
    if not session_files:
        logger.warning(f"Нет .session файлов в папке {sessions_dir}")
        return

    loaded = []
    for sf in session_files:
        session_path = str(sf.with_suffix(""))
        try:
            client = TelegramClient(session_path, api_id, api_hash)
            await client.connect()
            if await client.is_user_authorized():
                loaded.append(client)
                me = await client.get_me()
                name = f"@{me.username}" if me.username else str(me.id)
                logger.info(f"Сессия загружена: {name} ({sf.name})")
            else:
                logger.warning(f"Сессия не авторизована: {sf.name}")
                await client.disconnect()
        except Exception as e:
            logger.error(f"Ошибка загрузки сессии {sf.name}: {e}")

    _clients = loaded
    logger.info(f"Загружено сессий: {len(_clients)}")


async def get_client():
    global _client_index
    if not _clients:
        return None
    async with _lock:
        client = _clients[_client_index % len(_clients)]
        _client_index += 1
    return client


def has_sessions() -> bool:
    return len(_clients) > 0


def session_count() -> int:
    return len(_clients)


async def disconnect_all():
    for c in _clients:
        try:
            await c.disconnect()
        except Exception:
            pass


# ─── Interactive session creation ────────────────────────────────────────────

async def start_login(phone: str, api_id: int, api_hash: str, sessions_dir: str) -> str:
    """Send code to phone. Returns phone_code_hash."""
    from telethon import TelegramClient
    os.makedirs(sessions_dir, exist_ok=True)
    safe = phone.replace("+", "").replace(" ", "")
    session_path = os.path.join(sessions_dir, f"acc_{safe}")
    client = TelegramClient(session_path, api_id, api_hash)
    await client.connect()
    result = await client.send_code_request(phone)
    _pending_login[phone] = {"client": client, "hash": result.phone_code_hash, "path": session_path}
    return result.phone_code_hash


async def finish_login(phone: str, code: str) -> bool | str:
    """
    Complete login with code.
    Returns True on success, 'need_password' if 2FA required, False on failure.
    """
    from telethon.errors import SessionPasswordNeededError
    entry = _pending_login.get(phone)
    if not entry:
        return False
    client = entry["client"]
    try:
        await client.sign_in(phone, code, phone_code_hash=entry["hash"])
    except SessionPasswordNeededError:
        return "2fa"
    except Exception as e:
        logger.error(f"Login error: {e}")
        _pending_login.pop(phone, None)
        return False

    if await client.is_user_authorized():
        _clients.append(client)
        _pending_login.pop(phone, None)
        me = await client.get_me()
        logger.info(f"Новая сессия создана: @{me.username or me.id}")
        return True
    return False


async def finish_login_2fa(phone: str, password: str) -> bool:
    """Complete 2FA login with password."""
    entry = _pending_login.get(phone)
    if not entry:
        return False
    client = entry["client"]
    try:
        await client.sign_in(password=password)
    except Exception as e:
        logger.error(f"2FA login error: {e}")
        _pending_login.pop(phone, None)
        return False

    if await client.is_user_authorized():
        _clients.append(client)
        _pending_login.pop(phone, None)
        me = await client.get_me()
        logger.info(f"Новая сессия создана (2FA): @{me.username or me.id}")
        return True
    return False
