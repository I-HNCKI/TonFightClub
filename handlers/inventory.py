"""
Inventory: list items, equip/unequip; зелья с кнопкой «Выпить».
"""
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
from aiogram.utils.keyboard import InlineKeyboardBuilder

from keyboards import inventory_item_keyboard, inventory_list_keyboard
from database.db import db

router = Router(name="inventory")


def _inv_lines(items: list[dict]) -> list[str]:
    return [
        f"• {inv['name']} ({inv['slot']}) — урон {inv['min_damage']}-{inv['max_damage']}, +{inv['bonus_str']} сил, +{inv['bonus_hp']} HP"
        + (" [надето]" if inv["is_equipped"] else "")
        for inv in items
    ]


@router.message(F.text == "🎒 Инвентарь")
@router.message(Command("inv"))
async def inv_list(message: Message) -> None:
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

    items = await db.get_player_inventory(player["id"])
    potions = await db.get_player_potions(player["id"])

    text_parts = ["🎒 <b>Инвентарь</b>\n"]
    if items:
        text_parts.append("\n".join(_inv_lines(items)))
        text_parts.append("\n\nВыберите предмет:")
    else:
        text_parts.append("\nСнаряжение пусто.")
    if potions:
        text_parts.append("\n\n🧪 <b>Зелья</b>\n")
        for p in potions:
            text_parts.append(f"• {p['name']} x{p['quantity']}")
        text_parts.append("\nВыпить зелье — HP 100%, снимает травму:")
    text = "".join(text_parts)

    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    rows = []
    if items:
        kb_items = inventory_list_keyboard(items)
        rows.extend(kb_items.inline_keyboard)
    if potions:
        for p in potions:
            rows.append([InlineKeyboardButton(
                text=f"🧪 {p['name']} x{p['quantity']} — Выпить",
                callback_data=f"potion_drink_{p['item_id']}",
            )])
    kb = InlineKeyboardMarkup(inline_keyboard=rows) if rows else None

    if not items and not potions:
        await message.answer("Инвентарь пуст. Загляните в магазин.")
        return
    await message.answer(text, reply_markup=kb, parse_mode="HTML")


@router.callback_query(F.data.startswith("potion_drink_"))
async def potion_drink(callback: CallbackQuery) -> None:
    try:
        item_id = int(callback.data.split("_")[-1])
    except ValueError:
        await callback.answer("Ошибка")
        return
    player = await db.get_player_by_telegram_id(callback.from_user.id if callback.from_user else 0)
    if not player:
        await callback.answer("Сначала /start")
        return
    if await db.has_active_fight(player["id"]):
        await callback.answer("🛑 В бою зелье нельзя пить из инвентаря. Используйте кнопку «🧪 Хил».", show_alert=True)
        return
    ok, msg = await db.use_potion(player["id"], item_id)
    if ok:
        await callback.answer(msg)
        potions = await db.get_player_potions(player["id"])
        items = await db.get_player_inventory(player["id"])
        text = "🎒 <b>Инвентарь</b>\n\n"
        if items:
            text += "\n".join(_inv_lines(items)) + "\n\n"
        if potions:
            text += "🧪 <b>Зелья</b>\n" + "\n".join(f"• {p['name']} x{p['quantity']}" for p in potions)
        else:
            text += "🧪 Зелья закончились."
        from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
        from keyboards import inventory_list_keyboard
        rows = []
        if items:
            rows.extend(inventory_list_keyboard(items).inline_keyboard)
        if potions:
            for p in potions:
                rows.append([InlineKeyboardButton(
                    text=f"🧪 {p['name']} x{p['quantity']} — Выпить",
                    callback_data=f"potion_drink_{p['item_id']}",
                )])
        kb = InlineKeyboardMarkup(inline_keyboard=rows) if rows else None
        try:
            await callback.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
        except Exception:
            await callback.message.answer(text, reply_markup=kb, parse_mode="HTML")
    else:
        await callback.answer(msg, show_alert=True)


@router.callback_query(F.data.startswith("inv_equip_"))
async def inv_equip(callback: CallbackQuery) -> None:
    player = await db.get_player_by_telegram_id(callback.from_user.id if callback.from_user else 0)
    if not player:
        await callback.answer("Сначала /start")
        return

    if await db.has_active_fight(player["id"]):
        await callback.answer("🛑 Вы в бою! Сначала завершите поединок (выход = поражение).", show_alert=True)
        return

    try:
        inv_id = int(callback.data.split("_")[-1])
    except ValueError:
        await callback.answer("Ошибка")
        return
    
    ok = await db.set_equipped(inv_id, player["id"], True)
    if ok:
        items = await db.get_player_inventory(player["id"])
        await callback.message.edit_text(
            "🎒 <b>Инвентарь</b>\n\n" + "\n".join(_inv_lines(items)) + "\n\nВыберите предмет:",
            reply_markup=inventory_list_keyboard(items),
            parse_mode="HTML",
        )
        await callback.answer("Надето")
    else:
        await callback.answer("Не найдено в инвентаре")


@router.callback_query(F.data.startswith("inv_unequip_"))
async def inv_unequip(callback: CallbackQuery) -> None:
    player = await db.get_player_by_telegram_id(callback.from_user.id if callback.from_user else 0)
    if not player:
        await callback.answer("Сначала /start")
        return

    if await db.has_active_fight(player["id"]):
        await callback.answer("🛑 Вы в бою! Сначала завершите поединок (выход = поражение).", show_alert=True)
        return

    try:
        inv_id = int(callback.data.split("_")[-1])
    except ValueError:
        await callback.answer("Ошибка")
        return
    
    ok = await db.set_equipped(inv_id, player["id"], False)
    if ok:
        items = await db.get_player_inventory(player["id"])
        await callback.message.edit_text(
            "🎒 <b>Инвентарь</b>\n\n" + "\n".join(_inv_lines(items)) + "\n\nВыберите предмет:",
            reply_markup=inventory_list_keyboard(items),
            parse_mode="HTML",
        )
        await callback.answer("Снято")
    else:
        await callback.answer("Не найдено в инвентаре")


@router.callback_query(F.data == "inv_back")
async def inv_back(callback: CallbackQuery) -> None:
    await callback.answer()
    await callback.message.answer("Используйте кнопку «Инвентарь» в меню для просмотра списка.")