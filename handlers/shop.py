"""
Shop: buy items, sell items (50% price).
"""
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command

from keyboards import shop_buy_keyboard, shop_list_keyboard
from database.db import db

router = Router(name="shop")


@router.message(F.text == "🛒 Магазин")
@router.message(Command("shop"))
async def shop_menu(message: Message) -> None:
    
    player = await db.get_player_by_telegram_id(message.from_user.id if message.from_user else 0)
    if not player:
        await message.answer("Сначала /start")
        return
    stats = await db.get_combat_stats(player["id"])
    items = await db.get_shop_items()
    credits = stats.get("credits", 0)
    await message.answer(
        f"🛒 <b>Магазин</b>\n\nВаши кредиты: {credits}\n\nВыберите предмет:",
        reply_markup=shop_list_keyboard(items),
        parse_mode="HTML",
    )


@router.callback_query(F.data.startswith("shop_item_"))
async def shop_item_view(callback: CallbackQuery) -> None:
    try:
        item_id = int(callback.data.split("_")[-1])
    except ValueError:
        await callback.answer("Ошибка")
        return
    
    item = await db.get_item_by_id(item_id)
    if not item:
        await callback.answer("Предмет не найден")
        return
    text = (
        f"<b>{item['name']}</b>\n"
        f"Слот: {item['slot']}\n"
        f"Урон: {item['min_damage']}-{item['max_damage']}\n"
        f"Бонус силы: {item['bonus_str']}, бонус HP: {item['bonus_hp']}\n"
        f"Цена: {item['price']} кр."
    )
    await callback.message.answer(text, reply_markup=shop_buy_keyboard(item_id), parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data.startswith("shop_buy_"))
async def shop_buy(callback: CallbackQuery) -> None:
    try:
        item_id = int(callback.data.split("_")[-1])
    except ValueError:
        await callback.answer("Ошибка")
        return
    
    player = await db.get_player_by_telegram_id(callback.from_user.id if callback.from_user else 0)
    if not player:
        await callback.answer("Сначала /start")
        return
    ok, msg = await db.buy_item(player["id"], item_id)
    if ok:
        await callback.answer(msg)
        await callback.message.edit_text(callback.message.text + "\n\n✅ " + msg, parse_mode="HTML")
    else:
        await callback.answer(msg, show_alert=True)


@router.callback_query(F.data.startswith("shop_sell_"))
async def shop_sell(callback: CallbackQuery) -> None:
    try:
        inv_id = int(callback.data.split("_")[-1])
    except ValueError:
        await callback.answer("Ошибка")
        return
    
    player = await db.get_player_by_telegram_id(callback.from_user.id if callback.from_user else 0)
    if not player:
        await callback.answer("Сначала /start")
        return
    ok, msg, _ = await db.sell_item(player["id"], inv_id)
    if ok:
        await callback.answer(msg)
        await callback.message.edit_text(callback.message.text + "\n\n💰 " + msg, parse_mode="HTML")
    else:
        await callback.answer(msg, show_alert=True)
