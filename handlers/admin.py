"""
Админ-панель. Владелец 306039666; права админа можно выдавать по Telegram ID.
"""
import os
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardButton
from aiogram.filters import Command, CommandObject
from aiogram.utils.keyboard import InlineKeyboardBuilder

from database.db import db

router = Router(name="admin")

# Единственный владелец — только он может добавлять/удалять админов
OWNER_ID = 306039666


async def is_admin(user_id: int) -> bool:
    """Владелец или пользователь из таблицы admin_users."""
    if user_id == OWNER_ID:
        return True
    return await db.is_admin(user_id)


def _admin_keyboard():
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="💸 Снять кассу", callback_data="admin_withdraw")
    )
    return builder.as_markup()


@router.message(Command("admin"))
async def admin_panel(message: Message) -> None:
    if not message.from_user or not await is_admin(message.from_user.id):
        await message.answer("Команда не найдена.")
        return
    total_commission = await db.get_system_commission()
    players_count = await db.get_players_count()
    battles_count = await db.get_battles_count()
    await message.answer(
        "👑 <b>Админ-панель</b>\n\n"
        f"💰 Банк системы: <b>{total_commission}</b> кр.\n"
        f"👥 Игроков: {players_count}\n"
        f"⚔️ Боев: {battles_count}\n\n"
        "Снять кассу (обнулить банк и зафиксировать прибыль):\n\n"
        "<b>🛠 Управление:</b>\n"
        "/give_money [telegram_id] [сумма]\n"
        "/give_item [telegram_id] [item_id]\n"
        "/items_list — список ID вещей\n\n"
        "<b>👤 Права админа</b> (только владелец):\n"
        "/add_admin [telegram_id]\n"
        "/remove_admin [telegram_id]\n"
        "/admins_list — кто имеет права",
        reply_markup=_admin_keyboard(),
        parse_mode="HTML",
    )


@router.callback_query(F.data == "admin_withdraw")
async def admin_withdraw(callback: CallbackQuery) -> None:
    if not callback.from_user or not await is_admin(callback.from_user.id):
        await callback.answer()
        return
    await db.reset_commission()
    await callback.answer("Касса очищена! Прибыль зафиксирована.", show_alert=True)
    total_commission = await db.get_system_commission()
    players_count = await db.get_players_count()
    battles_count = await db.get_battles_count()
    try:
        await callback.message.edit_text(
            "👑 <b>Админ-панель</b>\n\n"
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
    if not callback.from_user or not await is_admin(callback.from_user.id):
        await callback.answer()
        return
    await db.reset_commission()
    await callback.answer("Касса очищена! Прибыль зафиксирована.", show_alert=True)
    total_commission = await db.get_system_commission()
    players_count = await db.get_players_count()
    battles_count = await db.get_battles_count()
    try:
        await callback.message.edit_text(
            "👑 <b>Админ-панель</b>\n\n"
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
    if not message.from_user or not await is_admin(message.from_user.id):
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
    if not message.from_user or not await is_admin(message.from_user.id):
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
    if not message.from_user or not await is_admin(message.from_user.id):
        await message.answer("Команда не найдена.")
        return
    await db.reset_commission()
    await message.answer("✅ Касса очищена! Прибыль зафиксирована.")


@router.message(Command("give_money"))
async def give_money(message: Message, command: CommandObject) -> None:
    if not message.from_user or not await is_admin(message.from_user.id):
        await message.answer("Команда не найдена.")
        return
    args = (command.args or "").strip().split()
    if len(args) != 2 or not args[0].isdigit() or not args[1].lstrip("-").isdigit():
        await message.answer("Использование: /give_money <telegram_id> <сумма>")
        return
    user_id = int(args[0])
    amount = int(args[1])
    ok = await db.admin_add_money(user_id, amount)
    if ok:
        await message.answer(f"✅ Игроку {user_id} начислено {amount} кр.")
    else:
        await message.answer("❌ Ошибка: Игрок не найден или неверные данные.")


@router.message(Command("give_item"))
async def give_item(message: Message, command: CommandObject) -> None:
    if not message.from_user or not await is_admin(message.from_user.id):
        await message.answer("Команда не найдена.")
        return
    args = (command.args or "").strip().split()
    if len(args) != 2 or not args[0].isdigit() or not args[1].isdigit():
        await message.answer("Использование: /give_item <telegram_id> <item_id>")
        return
    user_id = int(args[0])
    item_id = int(args[1])
    ok = await db.admin_add_item(user_id, item_id)
    if ok:
        await message.answer(f"✅ Игроку {user_id} выдан предмет ID {item_id}.")
    else:
        await message.answer("❌ Ошибка: Игрок или предмет не найден.")


@router.message(Command("create_item"))
async def create_item_cmd(message: Message, command: CommandObject) -> None:
    """God Mode: создать уникальный предмет и выдать игроку. type: weapon | armor."""
    if not message.from_user or not await is_admin(message.from_user.id):
        await message.answer("Команда не найдена.")
        return
    args = (command.args or "").strip().split()
    if len(args) < 4:
        await message.answer(
            "Использование: /create_item <player_id> <type> <stat> <название>\n"
            "Пример: /create_item 12345 weapon 100 Экскалибур"
        )
        return
    if not args[0].isdigit() or args[1].lower() not in ("weapon", "armor") or not args[2].isdigit():
        await message.answer("❌ Ошибка: player_id и stat — числа, type — weapon или armor.")
        return
    player_id = int(args[0])
    item_type = args[1].lower()
    stat = int(args[2])
    name = " ".join(args[3:]).strip()
    if not name:
        await message.answer("❌ Укажите название предмета.")
        return
    item_id = await db.create_custom_item(name, item_type, stat, price=0)
    if not item_id:
        await message.answer("❌ Ошибка создания предмета.")
        return
    ok = await db.admin_add_item(player_id, item_id)
    if not ok:
        await message.answer(f"✅ Предмет создан (ID {item_id}), но игрок {player_id} не найден.")
        return
    label = "Урон" if item_type == "weapon" else "Броня"
    await message.answer(f"✨ Создан и выдан предмет: {name} ({label}: {stat})")


@router.message(Command("items_list"))
async def items_list(message: Message) -> None:
    if not message.from_user or not await is_admin(message.from_user.id):
        await message.answer("Команда не найдена.")
        return
    items = await db.get_all_items_dict()
    lines = [f"ID: {it['id']} — {it['name']} ({it['type']})" for it in items]
    text = "📋 <b>Список предметов</b>\n\n" + "\n".join(lines) if lines else "Нет предметов в базе."
    await message.answer(text, parse_mode="HTML")


# ——— Права админа: только владелец ———

@router.message(Command("add_admin"))
async def add_admin_cmd(message: Message, command: CommandObject) -> None:
    """Выдать права админа по Telegram ID. Только владелец."""
    if not message.from_user or message.from_user.id != OWNER_ID:
        await message.answer("Команда не найдена.")
        return
    args = (command.args or "").strip().split()
    if len(args) != 1 or not args[0].isdigit():
        await message.answer("Использование: /add_admin <telegram_id>")
        return
    user_id = int(args[0])
    await db.add_admin(user_id)
    await message.answer(f"✅ Пользователю {user_id} выданы права админа.")


@router.message(Command("remove_admin"))
async def remove_admin_cmd(message: Message, command: CommandObject) -> None:
    """Забрать права админа по Telegram ID. Только владелец."""
    if not message.from_user or message.from_user.id != OWNER_ID:
        await message.answer("Команда не найдена.")
        return
    args = (command.args or "").strip().split()
    if len(args) != 1 or not args[0].isdigit():
        await message.answer("Использование: /remove_admin <telegram_id>")
        return
    user_id = int(args[0])
    ok = await db.remove_admin(user_id)
    if ok:
        await message.answer(f"✅ У пользователя {user_id} отозваны права админа.")
    else:
        await message.answer(f"Пользователь {user_id} не был в списке админов.")


@router.message(Command("admins_list"))
async def admins_list(message: Message) -> None:
    """Список ID с правами админа. Доступно всем админам."""
    if not message.from_user or not await is_admin(message.from_user.id):
        await message.answer("Команда не найдена.")
        return
    ids = await db.get_admin_ids()
    lines = [f"• {OWNER_ID} (владелец)"] + [f"• {tid}" for tid in ids]
    text = "👤 <b>Права админа</b>\n\n" + "\n".join(lines)
    await message.answer(text, parse_mode="HTML")


@router.message(Command("admin_users"))
async def admin_users(message: Message) -> None:
    """Список всех зарегистрированных игроков. Доступ только для ADMIN_ID из .env."""
    try:
        admin_id = int(os.getenv("ADMIN_ID", "0").strip())
    except (ValueError, TypeError):
        admin_id = 0
    if not message.from_user or message.from_user.id != admin_id:
        await message.answer("Команда не найдена.")
        return
    players = await db.get_all_players_with_level()
    if not players:
        await message.answer("Список игроков пуст.")
        return
    lines = []
    for p in players:
        username = p.get("username")
        name = f"@{username}" if username and not username.startswith("@") else (username or "Боец")
        tid = p.get("telegram_id", 0)
        lvl = p.get("level", 1)
        lines.append(f"👤 Игрок: {name} (ID: {tid}) | Уровень: {lvl}")
    await message.answer("\n".join(lines), parse_mode="HTML")
