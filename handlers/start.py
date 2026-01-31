"""
Registration and /start.
Fixes username updates.
"""
from aiogram import Router
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
    
    effective_name = (user.username or user.first_name or "Боец").replace("<", "").replace(">", "")[:25]
    player = await db.get_or_create_player(user.id, effective_name)
    await db.update_player_name(user.id, effective_name)

    await message.answer(
        f"👋 Добро пожаловать, <b>{effective_name}</b>!\n\n"
        "🛡 <b>Тон Бойцовский Клуб</b>\n"
        "Качайся, покупай снаряжение и сражайся на Арене.\n\n"
        "<i>Нажми <b>/help</b> или кнопку <b>Помощь</b>, если запутался.</i>",
        reply_markup=main_menu(),
        parse_mode="HTML"
    )