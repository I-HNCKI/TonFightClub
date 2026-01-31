"""
Profile: show stats, upgrade with free_points, выбор класса при 2+ уровне.
"""
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
from aiogram.utils.keyboard import InlineKeyboardBuilder, InlineKeyboardButton

from keyboards import main_menu, profile_upgrade_keyboard, profile_upgrade_keyboard_with_top
from database.db import db  

router = Router(name="profile")

CLASS_LABELS = {"rogue": "Ловкач", "tank": "Танк", "warrior": "Мастер"}
CLASS_EMOJI = {"rogue": "🗡", "tank": "🛡", "warrior": "⚔️"}


def format_stats(stats: dict, player_class: str | None = None) -> str:
    credits = stats.get("credits", 0)
    level = stats.get("level", 1)
    class_line = ""
    if player_class:
        label = CLASS_LABELS.get(player_class, player_class)
        emoji = CLASS_EMOJI.get(player_class, "👤")
        class_line = f"👤 Класс: {label} {emoji}\n"
    return (
        f"📋 <b>Профиль</b>\n\n"
        f"{class_line}"
        f"🎖 Уровень: {level}\n"
        f"💰 Баланс: {credits} кр.\n"
        f"📊 Опыт: {stats.get('experience', 0)}\n"
        f"❤️ HP: {stats.get('hp', 0)}\n\n"
        f"Сила: {stats.get('strength', 0)} [+]\n"
        f"Ловкость: {stats.get('agility', 0)} [+]\n"
        f"Интуиция: {stats.get('intuition', 0)} [+]\n"
        f"Выносливость: {stats.get('stamina', 0)} [+]\n\n"
        f"🎖 Очки статов (свободные): <b>{stats.get('free_points', 0)}</b>\n\n"
        f"Распределите очки статов (кнопки ниже):"
    )


def class_choice_keyboard():
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="🗡 Ловкач", callback_data="class_rogue"),
        InlineKeyboardButton(text="🛡 Танк", callback_data="class_tank"),
        InlineKeyboardButton(text="⚔️ Мастер", callback_data="class_warrior"),
    )
    return builder.as_markup()


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
    player_class = player.get("player_class")
    level = stats.get("level", 1)
    if not player_class and level >= 2:
        await message.answer(
            "📋 <b>Выбор класса</b>\n\n"
            "Достигнут 2-й уровень. Выберите класс:\n"
            "🗡 <b>Ловкач</b> — крит и урон от ловкости (оружие rogue).\n"
            "🛡 <b>Танк</b> — много HP и брони от выносливости (полный сет).\n"
            "⚔️ <b>Мастер</b> — урон и блок от силы (оружие warrior).",
            reply_markup=class_choice_keyboard(),
            parse_mode="HTML",
        )
        return
    await message.answer(
        format_stats(stats, player_class),
        reply_markup=profile_upgrade_keyboard_with_top(),
        parse_mode="HTML",
    )


@router.callback_query(F.data.startswith("class_"))
async def profile_class_choice(callback: CallbackQuery) -> None:
    player = await db.get_player_by_telegram_id(callback.from_user.id if callback.from_user else 0)
    if not player:
        await callback.answer("Сначала /start")
        return
    if callback.data == "class_rogue":
        class_type = "rogue"
    elif callback.data == "class_tank":
        class_type = "tank"
    elif callback.data == "class_warrior":
        class_type = "warrior"
    else:
        await callback.answer()
        return
    ok = await db.set_player_class(player["id"], class_type)
    if not ok:
        await callback.answer("Ошибка выбора класса", show_alert=True)
        return
    stats = await db.get_combat_stats(player["id"])
    label = CLASS_LABELS.get(class_type, class_type)
    await callback.message.edit_text(
        format_stats(stats, class_type),
        reply_markup=profile_upgrade_keyboard(),
        parse_mode="HTML",
    )
    await callback.answer(f"Класс установлен: {label}")


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
    player = await db.get_player_by_telegram_id(callback.from_user.id if callback.from_user else 0)
    player_class = player.get("player_class") if player else None
    await callback.message.edit_text(
        format_stats(stats, player_class),
        reply_markup=profile_upgrade_keyboard_with_top(),
        parse_mode="HTML",
    )
    await callback.answer("+1 к стату")
