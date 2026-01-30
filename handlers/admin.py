"""
Админ-панель владельца. Доступ только по ID: 413550666, 695574514.
"""
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardButton
from aiogram.filters import Command, CommandObject
from aiogram.utils.keyboard import InlineKeyboardBuilder

from database.db import db

router = Router(name="admin")

ADMIN_IDS = [413550666, 695574514]


def _admin_keyboard():
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="💸 Снять кассу", callback_data="admin_withdraw")
    )
    return builder.as_markup()


@router.message(Command("admin"))
async def admin_panel(message: Message) -> None:
    if message.from_user and message.from_user.id not in ADMIN_IDS:
        await message.answer("Команда не найдена.")
        return
    total_commission = await db.get_system_commission()
    players_count = await db.get_players_count()
    battles_count = await db.get_battles_count()
    await message.answer(
        "👑 <b>Админ-панель владельца</b>\n\n"
        f"💰 Банк системы: <b>{total_commission}</b> кр.\n"
        f"👥 Игроков: {players_count}\n"
        f"⚔️ Боев: {battles_count}\n\n"
        "Снять кассу (обнулить банк и зафиксировать прибыль):",
        reply_markup=_admin_keyboard(),
        parse_mode="HTML",
    )


@router.callback_query(F.data == "admin_withdraw")
async def admin_withdraw(callback: CallbackQuery) -> None:
    if callback.from_user and callback.from_user.id not in ADMIN_IDS:
        await callback.answer()
        return
    await db.reset_commission()
    await callback.answer("Касса очищена! Прибыль зафиксирована.", show_alert=True)
    total_commission = await db.get_system_commission()
    players_count = await db.get_players_count()
    battles_count = await db.get_battles_count()
    try:
        await callback.message.edit_text(
            "👑 <b>Админ-панель владельца</b>\n\n"
            f"💰 Банк системы: <b>{total_commission}</b> кр.\n"
            f"👥 Игроков: {players_count}\n"
            f"⚔️ Боев: {battles_count}\n\n"
            "Касса снята. Прибыль зафиксирована.",
            reply_markup=_admin_keyboard(),
            parse_mode="HTML",
        )
    except Exception:
        pass


@router.callback_query(F.data == "admin_clear_cash")
async def admin_clear_cash(callback: CallbackQuery) -> None:
    """Обратная совместимость: перенаправляем на admin_withdraw."""
    if callback.from_user and callback.from_user.id not in ADMIN_IDS:
        await callback.answer()
        return
    await db.reset_commission()
    await callback.answer("Касса очищена! Прибыль зафиксирована.", show_alert=True)
    total_commission = await db.get_system_commission()
    players_count = await db.get_players_count()
    battles_count = await db.get_battles_count()
    try:
        await callback.message.edit_text(
            "👑 <b>Админ-панель владельца</b>\n\n"
            f"💰 Банк системы: <b>{total_commission}</b> кр.\n"
            f"👥 Игроков: {players_count}\n"
            f"⚔️ Боев: {battles_count}\n\n"
            "Касса снята. Прибыль зафиксирована.",
            reply_markup=_admin_keyboard(),
            parse_mode="HTML",
        )
    except Exception:
        pass


@router.message(Command("admin_money"))
async def admin_add_money(message: Message, command: CommandObject) -> None:
    if message.from_user and message.from_user.id not in ADMIN_IDS:
        await message.answer("Команда не найдена.")
        return
    if not command.args or not command.args.strip().isdigit():
        await message.answer("Использование: /admin_money 1000")
        return
    amount = int(command.args.strip())
    player = await db.get_player_by_telegram_id(message.from_user.id)
    if player:
        await db.add_credits(player["id"], amount)
        await message.answer(f"✅ Выдано {amount} кредитов.")
    else:
        await message.answer("Сначала /start")


@router.message(Command("admin_lvl"))
async def admin_set_level(message: Message, command: CommandObject) -> None:
    if message.from_user and message.from_user.id not in ADMIN_IDS:
        await message.answer("Команда не найдена.")
        return
    if not command.args or not command.args.strip().isdigit():
        await message.answer("Использование: /admin_lvl 100")
        return
    amount = int(command.args.strip())
    player = await db.get_player_by_telegram_id(message.from_user.id)
    if player:
        await db.add_experience(player["id"], amount)
        await message.answer(f"✅ Выдано {amount} опыта.")
    else:
        await message.answer("Ошибка")


@router.message(Command("reset_commission"))
async def admin_reset_commission_cmd(message: Message) -> None:
    if message.from_user and message.from_user.id not in ADMIN_IDS:
        await message.answer("Команда не найдена.")
        return
    await db.reset_commission()
    await message.answer("✅ Касса очищена! Прибыль зафиксирована.")
