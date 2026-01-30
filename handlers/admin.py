from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardButton
from aiogram.filters import Command, CommandObject
from aiogram.utils.keyboard import InlineKeyboardBuilder

from database.db import db

router = Router(name="admin")

ADMIN_IDS = [413550666, 695574514]


@router.message(Command("admin"))
async def admin_panel(message: Message) -> None:
    if message.from_user.id not in ADMIN_IDS:
        return
    commission = await db.get_system_commission()
    players_count = await db.get_players_count()
    battles_count = await db.get_battles_count()
    top3 = await db.get_top_rich(3)
    top_str = "\n".join(
        f"  {i+1}. {(r.get('username') or 'Боец')[:20]} — {r['credits']} кр."
        for i, r in enumerate(top3)
    )
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="🗑 Очистить кассу", callback_data="admin_clear_cash")
    )
    await message.answer(
        "👑 <b>Админ-панель владельца</b>\n\n"
        f"💰 Накопленная комиссия: <b>{commission}</b> кр.\n"
        f"👥 Игроков: {players_count}\n"
        f"⚔ Боев: {battles_count}\n\n"
        f"<b>Топ-3 богачей:</b>\n{top_str or '—'}\n\n"
        "Очистить кассу (обнулить комиссию):",
        reply_markup=builder.as_markup(),
        parse_mode="HTML",
    )


@router.callback_query(F.data == "admin_clear_cash")
async def admin_clear_cash(callback: CallbackQuery) -> None:
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer()
        return
    await db.reset_commission()
    await callback.answer("Касса обнулена.")
    commission = await db.get_system_commission()
    players_count = await db.get_players_count()
    battles_count = await db.get_battles_count()
    top3 = await db.get_top_rich(3)
    top_str = "\n".join(
        f"  {i+1}. {(r.get('username') or 'Боец')[:20]} — {r['credits']} кр."
        for i, r in enumerate(top3)
    )
    try:
        await callback.message.edit_text(
            "👑 <b>Админ-панель</b>\n\n"
            f"💰 Комиссия: <b>{commission}</b> кр. (обнулена)\n"
            f"👥 Игроков: {players_count}\n"
            f"⚔ Боев: {battles_count}\n\n"
            f"<b>Топ-3 богачей:</b>\n{top_str or '—'}",
            reply_markup=callback.message.reply_markup,
            parse_mode="HTML",
        )
    except Exception:
        pass


@router.message(Command("admin_money"))
async def admin_add_money(message: Message, command: CommandObject) -> None:
    if message.from_user.id not in ADMIN_IDS:
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
    if message.from_user.id not in ADMIN_IDS:
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
async def admin_reset_commission(message: Message) -> None:
    if message.from_user.id not in ADMIN_IDS:
        return
    await db.reset_commission()
    await message.answer("✅ Комиссия обнулена.")
