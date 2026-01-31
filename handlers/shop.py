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
    if await db.has_active_fight(player["id"]):
        await message.answer(
            "🛑 <b>Вы в бою!</b>\n\nСначала завершите поединок (выход = поражение).",
            parse_mode="HTML",
        )
        return
        
    stats = await db.get_combat_stats(player["id"])
    items = await db.get_shop_items()
    credits = stats.get("credits", 0)
    player_class = player.get("player_class")
    await message.answer(
        f"🛒 <b>Магазин</b>\n\nВаши кредиты: {credits}\n\nВыберите предмет:",
        reply_markup=shop_list_keyboard(items, player_class),
        parse_mode="HTML",
    )


@router.callback_query(F.data.startswith("shop_item_"))
async def shop_item_view(callback: CallbackQuery) -> None:
    player = await db.get_player_by_telegram_id(callback.from_user.id if callback.from_user else 0)
    if player and await db.has_active_fight(player["id"]):
        await callback.answer("🛑 Вы в бою! Сначала завершите поединок (выход = поражение).", show_alert=True)
        return
    try:
        item_id = int(callback.data.split("_")[-1])
    except ValueError:
        await callback.answer("Ошибка")
        return
    item = await db.get_item_by_id(item_id)
    if not item:
        await callback.answer("Предмет не найден")
        return
    price = item.get("price", 0)
    slot = item.get("slot", "")
    min_level = item.get("min_level", 1) or 1
    level_line = f"🎖 Требуемый уровень: {min_level}\n\n"
    slot_names = {"head": "Голова (Шлем)", "body": "Тело (Доспех)", "legs": "Ноги (Обувь)", "weapon": "Оружие", "potion": "Зелье"}
    slot_label = slot_names.get(slot, slot)
    if slot == "potion":
        heal_pct = item.get("heal_percent", 30) or 30
        trauma = " Снимает травму." if item.get("removes_trauma") else ""
        text = (
            f"<b>🧪 {item['name']}</b>\n\n"
            f"Восстанавливает <b>{heal_pct}%</b> от макс. HP.{trauma}\n"
            "В бою: 1 раз за бой (не тратит ход).\n\n"
            f"{level_line}<b>💰 Цена: {price} кредитов</b>"
        )
    else:
        class_type = item.get("class_type", "all")
        class_label = "Все" if class_type == "all" else {"rogue": "Ловкач", "tank": "Танк", "warrior": "Мастер"}.get(class_type, class_type)
        dmg_line = f"Урон: {item['min_damage']}-{item['max_damage']}\n" if (item.get("min_damage") or item.get("max_damage")) else ""
        armor_line = f"Броня: {item.get('armor', 0)}\n" if item.get("armor") else ""
        text = (
            f"<b>{item['name']}</b>\n"
            f"Слот: {slot_label} | Класс: {class_label}\n"
            f"{dmg_line}{armor_line}\n"
            f"{level_line}<b>💰 Цена: {price} кредитов</b>"
        )
    await callback.message.answer(text, reply_markup=shop_buy_keyboard(item_id), parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data.startswith("shop_buy_"))
async def shop_buy(callback: CallbackQuery) -> None:
    player = await db.get_player_by_telegram_id(callback.from_user.id if callback.from_user else 0)
    if not player:
        await callback.answer("Сначала /start")
        return
    if await db.has_active_fight(player["id"]):
        await callback.answer("🛑 Вы в бою! Сначала завершите поединок (выход = поражение).", show_alert=True)
        return
    try:
        item_id = int(callback.data.split("_")[-1])
    except ValueError:
        await callback.answer("Ошибка")
        return
    ok, msg = await db.buy_item(player["id"], item_id)
    if ok:
        await callback.answer(msg)
        await callback.message.edit_text(
            callback.message.text + "\n\n✅ " + msg,
            parse_mode="HTML",
        )
    else:
        await callback.answer(msg, show_alert=True)


@router.callback_query(F.data.startswith("shop_sell_"))
async def shop_sell(callback: CallbackQuery) -> None:
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
    ok, msg, _ = await db.sell_item(player["id"], inv_id)
    if ok:
        await callback.answer(msg)
        await callback.message.edit_text(callback.message.text + "\n\n💰 " + msg, parse_mode="HTML")
    else:
        await callback.answer(msg, show_alert=True)
