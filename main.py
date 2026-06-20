import asyncio
import logging
import sys
from dotenv import load_dotenv

load_dotenv()

from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from aiogram.fsm.storage.memory import MemoryStorage

from bot.config import BOT_TOKEN, API_ID, API_HASH, SESSIONS_DIR, API_PORT
from bot.database import init_db
from bot.handlers import start, search, premium, profile, referrals, admin
from bot.handlers import bulk_search, history, api_info
from bot.utils.scheduler import trap_scheduler

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    stream=sys.stdout,
)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("telethon").setLevel(logging.WARNING)
logging.getLogger("aiohttp").setLevel(logging.WARNING)

logger = logging.getLogger(__name__)


async def main():
    if not BOT_TOKEN:
        logger.error("BOT_TOKEN не установлен!")
        sys.exit(1)

    await init_db()
    logger.info("База данных инициализирована")

    from bot.utils.session_manager import load_sessions
    await load_sessions(API_ID, API_HASH, SESSIONS_DIR)

    bot = Bot(
        token=BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )

    from bot.utils.username_checker import set_bot
    set_bot(bot)

    dp = Dispatcher(storage=MemoryStorage())
    dp.include_router(start.router)
    dp.include_router(search.router)
    dp.include_router(premium.router)
    dp.include_router(profile.router)
    dp.include_router(referrals.router)
    dp.include_router(admin.router)
    dp.include_router(bulk_search.router)
    dp.include_router(history.router)
    dp.include_router(api_info.router)

    me = await bot.get_me()
    logger.info(f"Бот запущен: @{me.username}")

    from api_server import start_api_server
    api_runner = await start_api_server(API_PORT)
    logger.info(f"API сервер: http://0.0.0.0:{API_PORT}/api/v1/status")

    # Scheduler polls every 60 seconds; each trap has its own interval
    asyncio.create_task(trap_scheduler(bot, interval=60))

    try:
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    finally:
        await api_runner.cleanup()


if __name__ == "__main__":
    asyncio.run(main())
