"""
Shop: buy items, sell items (50% price). Пагинация по 5 предметов на страницу.
"""
import re
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command

from keyboards import shop_buy_keyboard, shop_list_keyboard_paginated
from database.db import db

router = Router(name="shop")

SHOP_PAGE_SIZE = 5


def _shop_item_line(it: dict) -> str:
    """Одна строка списка: 🧪 Малое зелье (+50% ❤️) — 5 💰 или Оружие — 1 💰."""
    if it.get("slot") == "potion":
        hp = it.get("heal_percent") or 30
        return f"🧪 {it['name']} (+{hp}% ❤️) — {it['price']} 💰"
    return f"{it['name']} — {it['price']} 💰"


def _shop_page_text(items_page: list[dict], credits: int, page: int, total_pages: int) -> str:
    lines = [
        "🛒 <b>Магазин</b>\n",
        f"Ваши кредиты: {credits}\n",
        "Выберите предмет:",
    ]
    for it in items_page:
        lines.append(_shop_item_line(it))
    lines.append(f"\nСтр. {page}/{total_pages}")
    return "\n".join(lines)


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
    total_pages = max(1, (len(items) + SHOP_PAGE_SIZE - 1) // SHOP_PAGE_SIZE)
    page = 1
    chunk = items[(page - 1) * SHOP_PAGE_SIZE : page * SHOP_PAGE_SIZE]
    text = _shop_page_text(chunk, credits, page, total_pages)
    await message.answer(
        text,
        reply_markup=shop_list_keyboard_paginated(chunk, page, total_pages),
        parse_mode="HTML",
    )


@router.callback_query(F.data.startswith("shop_page_"))
async def shop_page(callback: CallbackQuery) -> None:
    """Пагинация магазина: обновить сообщение на страницу N."""
    player = await db.get_player_by_telegram_id(callback.from_user.id if callback.from_user else 0)
    if not player:
        await callback.answer("Сначала /start")
        return
    if await db.has_active_fight(player["id"]):
        await callback.answer("🛑 Вы в бою!", show_alert=True)
        return
    try:
        page = int(callback.data.replace("shop_page_", ""))
    except ValueError:
        page = 1
    stats = await db.get_combat_stats(player["id"])
    items = await db.get_shop_items()
    credits = stats.get("credits", 0)
    total_pages = max(1, (len(items) + SHOP_PAGE_SIZE - 1) // SHOP_PAGE_SIZE)
    page = max(1, min(page, total_pages))
    chunk = items[(page - 1) * SHOP_PAGE_SIZE : page * SHOP_PAGE_SIZE]
    text = _shop_page_text(chunk, credits, page, total_pages)
    kb = shop_list_keyboard_paginated(chunk, page, total_pages)
    await callback.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    await callback.answer()


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


def _parse_shop_page_from_text(text: str | None) -> int:
    """Из текста сообщения магазина извлечь номер страницы (Стр. N/M)."""
    if not text:
        return 1
    m = re.search(r"Стр\.\s*(\d+)/\d+", text)
    return int(m.group(1)) if m else 1


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
        # Если сообщение — страница магазина, обновляем её (актуальные кредиты и клавиатура)
        page = _parse_shop_page_from_text(callback.message.text)
        stats = await db.get_combat_stats(player["id"])
        items = await db.get_shop_items()
        credits = stats.get("credits", 0)
        total_pages = max(1, (len(items) + SHOP_PAGE_SIZE - 1) // SHOP_PAGE_SIZE)
        page = max(1, min(page, total_pages))
        chunk = items[(page - 1) * SHOP_PAGE_SIZE : page * SHOP_PAGE_SIZE]
        text = _shop_page_text(chunk, credits, page, total_pages) + "\n\n✅ " + msg
        kb = shop_list_keyboard_paginated(chunk, page, total_pages)
        await callback.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
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
