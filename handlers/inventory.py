"""
Inventory: list items, equip/unequip.
"""
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command

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
    items = await db.get_player_inventory(player["id"])
    if not items:
        await message.answer("Инвентарь пуст. Загляните в магазин или побейте манекен.")
        return
    await message.answer(
        "🎒 <b>Инвентарь</b>\n\n" + "\n".join(_inv_lines(items)) + "\n\nВыберите предмет:",
        reply_markup=inventory_list_keyboard(items),
        parse_mode="HTML",
    )


@router.callback_query(F.data.startswith("inv_equip_"))
async def inv_equip(callback: CallbackQuery) -> None:
    try:
        inv_id = int(callback.data.split("_")[-1])
    except ValueError:
        await callback.answer("Ошибка")
        return
    
    player = await db.get_player_by_telegram_id(callback.from_user.id if callback.from_user else 0)
    if not player:
        await callback.answer("Сначала /start")
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
    try:
        inv_id = int(callback.data.split("_")[-1])
    except ValueError:
        await callback.answer("Ошибка")
        return
    
    player = await db.get_player_by_telegram_id(callback.from_user.id if callback.from_user else 0)
    if not player:
        await callback.answer("Сначала /start")
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
    # Could resend inventory list
    await callback.message.answer("Используйте кнопку «Инвентарь» в меню для просмотра списка.")
