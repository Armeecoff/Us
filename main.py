import asyncio
import logging
import sys
from dotenv import load_dotenv

load_dotenv()

from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from aiogram.fsm.storage.memory import MemoryStorage

from bot.config import BOT_TOKEN, API_ID, API_HASH, SESSIONS_DIR, HOST, PORT, MAX_SESSIONS
from bot.database import init_db
from bot.handlers import start, search, premium, profile, referrals, admin
from bot.handlers import bulk_search, history, api_info
from bot.utils.scheduler import trap_scheduler
from bot.utils.username_checker import init_client_pool, close_all_clients

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

    # Инициализация базы данных
    await init_db()
    logger.info("База данных инициализирована")

    # Инициализация пула Telegram-клиентов (для мультипоточности)
    await init_client_pool()
    logger.info(f"Пул сессий инициализирован (макс. {MAX_SESSIONS} клиентов)")

    # Создаём бота
    bot = Bot(
        token=BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )

    # Передаём бота в username_checker (для Bot API fallback)
    from bot.utils.username_checker import set_bot
    set_bot(bot)

    # Диспетчер
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

    # Запуск API-сервера (на HOST:PORT из config)
    from api_server import start_api_server
    api_runner = await start_api_server(host=HOST, port=PORT)
    logger.info(f"API сервер запущен на http://{HOST}:{PORT}/api/v1/status")

    # Запуск планировщика ловушек (каждые 60 секунд)
    asyncio.create_task(trap_scheduler(bot, interval=60))

    try:
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    finally:
        # Закрываем все сессии и API сервер при завершении
        await close_all_clients()
        await api_runner.cleanup()
        await bot.session.close()
        logger.info("Бот остановлен")


if __name__ == "__main__":
    asyncio.run(main())
