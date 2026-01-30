"""
Entry point: bot, dp, database, routers.
"""
import asyncio
import logging
import os

from dotenv import load_dotenv
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from database.db import db
# 1. ДОБАВИЛ top В ИМПОРТЫ
from handlers import start, profile, battle, arena, inventory, shop, top

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise ValueError("Set BOT_TOKEN in .env")


async def main() -> None:
    bot = Bot(
        token=BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = Dispatcher()
    
    await db.connect()

    # Подключаем роутеры (обработчики команд)
    dp.include_router(start.router)
    dp.include_router(profile.router)
    dp.include_router(battle.router)
    dp.include_router(arena.router)
    dp.include_router(inventory.router)
    dp.include_router(shop.router)
    # 2. ПОДКЛЮЧИЛ РОУТЕР ТОПА
    dp.include_router(top.router)

    try:
        logger.info("Bot starting...")
        await dp.start_polling(bot)
    finally:
        await db.close()
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())