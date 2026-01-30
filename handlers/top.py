from aiogram import Router, F
from aiogram.types import Message
from aiogram.filters import Command

from database.db import db

router = Router(name="top")

@router.message(F.text == "🏆 Топ игроков")
@router.message(Command("top"))
async def show_leaderboard(message: Message) -> None:
    # 1. Запрашиваем данные из базы
    leaders = await db.get_top_players(10)
    
    if not leaders:
        await message.answer("В этом мире пока нет героев...")
        return

    # 2. Красиво оформляем текст
    text = "🏆 <b>Топ-10 бойцов</b>\n\n"
    
    medals = {1: "🥇", 2: "🥈", 3: "🥉"}
    
    for i, player in enumerate(leaders, 1):
        # Если есть медалька (1-3 место), ставим её, иначе просто цифру
        icon = medals.get(i, "▪️")
        name = player["username"] or "Неизвестный"
        lvl = player["level"]
        
        text += f"{icon} <b>{name}</b> — {lvl} ур.\n"

    text += "\n<i>Стань сильнее, чтобы попасть сюда!</i>"

    # 3. Отправляем
    await message.answer(text, parse_mode="HTML")