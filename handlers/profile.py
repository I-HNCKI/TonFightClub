"""
Profile: show stats, upgrade with free_points.
"""
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command

from keyboards import main_menu, profile_upgrade_keyboard
from database.db import db  

router = Router(name="profile")


def format_stats(stats: dict) -> str:
    return (
        f"📋 <b>Профиль</b>\n\n"
        f"Сила: {stats.get('strength', 0)} [+]\n"
        f"Ловкость: {stats.get('agility', 0)} [+]\n"
        f"Интуиция: {stats.get('intuition', 0)} [+]\n"
        f"Выносливость: {stats.get('stamina', 0)} [+]\n"
        f"HP: {stats.get('hp', 0)}\n\n"
        f"🎖 Очки статов (свободные): <b>{stats.get('free_points', 0)}</b>\n"
        f"💰 Кредиты: {stats.get('credits', 0)}\n"
        f"📊 Опыт: {stats.get('experience', 0)} | Уровень: {stats.get('level', 1)}\n\n"
        f"Распределите очки статов (кнопки ниже):"
    )


@router.message(F.text == "📋 Профиль")
@router.message(Command("profile"))
async def profile_menu(message: Message) -> None:
    player = await db.get_player_by_telegram_id(message.from_user.id if message.from_user else 0)
    if not player:
        await message.answer("Сначала /start")
        return
    if await db.has_active_fight(player["id"]):
        await message.answer(
            "🛑 <b>Вы в бою!</b>\n\nСначала завершите поединок (выход = поражение).",
            parse_mode="HTML",
        )
        return
    stats = await db.get_combat_stats(player["id"])
    if not stats:
        await message.answer("Ошибка загрузки статов.")
        return
    await message.answer(
        format_stats(stats),
        reply_markup=profile_upgrade_keyboard(),
        parse_mode="HTML",
    )


@router.callback_query(F.data.startswith("stat_"))
async def profile_upgrade(callback: CallbackQuery) -> None:
    player = await db.get_player_by_telegram_id(callback.from_user.id if callback.from_user else 0)
    if not player:
        await callback.answer("Сначала /start")
        return
    if await db.has_active_fight(player["id"]):
        await callback.answer("🛑 Вы в бою! Сначала завершите поединок (выход = поражение).", show_alert=True)
        return
    if callback.data == "stat_strength":
        stat = "strength"
    elif callback.data == "stat_agility":
        stat = "agility"
    elif callback.data == "stat_intuition":
        stat = "intuition"
    elif callback.data == "stat_stamina":
        stat = "stamina"
    else:
        await callback.answer("Неизвестная кнопка")
        return
    ok = await db.upgrade_stat(player["id"], stat)
    if not ok:
        await callback.answer("Нет свободных очков")
        return
    stats = await db.get_combat_stats(player["id"])
    await callback.message.edit_text(
        format_stats(stats),
        reply_markup=profile_upgrade_keyboard(),
        parse_mode="HTML",
    )
    await callback.answer("+1 к стату")
