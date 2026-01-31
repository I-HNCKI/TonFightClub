"""
Entry point: bot, dp, database, routers.
"""
import os
from dotenv import load_dotenv

load_dotenv()

import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from database.db import db
from handlers import start, profile, shadow_fight, arena, inventory, shop, top, admin, help

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

    dp.include_router(start.router)
    dp.include_router(profile.router)
    dp.include_router(shadow_fight.router)
    dp.include_router(arena.router)
    dp.include_router(inventory.router)
    dp.include_router(shop.router)
    dp.include_router(top.router)
    dp.include_router(admin.router)
    dp.include_router(help.router)

    try:
        logger.info("Bot starting...")
        await dp.start_polling(bot)
    finally:
        await db.close()
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())