import asyncio
import logging
from datetime import datetime
from bot.database import (
    get_all_active_traps, mark_trap_notified, update_trap_last_checked,
    is_premium, is_luxe
)
from bot.utils.username_checker import is_username_free

logger = logging.getLogger(__name__)


def _should_check(trap) -> bool:
    interval = trap["check_interval"] or 1800
    last = trap["last_checked_at"]
    if not last:
        return True
    try:
        elapsed = (datetime.now() - datetime.fromisoformat(last)).total_seconds()
        return elapsed >= interval
    except Exception:
        return True


async def check_traps(bot):
    traps = await get_all_active_traps()
    for trap in traps:
        try:
            if not _should_check(trap):
                continue
            await update_trap_last_checked(trap["id"])
            free = await is_username_free(trap["target_username"])
            if free:
                await mark_trap_notified(trap["id"])
                interval_min = (trap["check_interval"] or 1800) // 60
                await bot.send_message(
                    trap["user_id"],
                    f"🪤 <b>Ловушка сработала!</b>\n\n"
                    f"Ник <code>@{trap['target_username']}</code> стал свободным!\n\n"
                    f"⚡️ Скорее регистрируй: t.me/{trap['target_username']}",
                    parse_mode="HTML"
                )
        except Exception as e:
            logger.error(f"Trap check error for {trap['target_username']}: {e}")
        await asyncio.sleep(0.3)


async def trap_scheduler(bot, interval: int = 60):
    while True:
        try:
            await check_traps(bot)
        except Exception as e:
            logger.error(f"Scheduler error: {e}")
        await asyncio.sleep(interval)
