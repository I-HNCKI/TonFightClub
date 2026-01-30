"""
Registration and /start.
"""
from aiogram import Router, F
from aiogram.types import Message
from aiogram.filters import CommandStart

from keyboards import main_menu
from database.db import db

router = Router(name="start")


@router.message(CommandStart())
async def cmd_start(message: Message) -> None:
    
    user = message.from_user
    if not user:
        return
    player = await db.get_or_create_player(user.id, user.username)
    if player:
        await message.answer(
            "Добро пожаловать в боевую арену!\n\n"
            "Используйте меню: Профиль, Бой с манекеном, Инвентарь, Магазин, Арена PvP.",
            reply_markup=main_menu(),
        )
