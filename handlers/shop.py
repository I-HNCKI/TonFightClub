"""
Shop: каталог по категориям — Оружие, Одежда, Эликсиры. Пагинация по уровням (1–5) для оружия и одежды.
"""
import re
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command

from keyboards import (
    shop_buy_keyboard,
    shop_main_menu_keyboard,
    shop_category_level_keyboard,
    shop_elixirs_keyboard,
)
from database.db import db

router = Router(name="shop")

SHOP_MAX_LEVEL = 5


def _elixir_line(it: dict) -> str:
    """Строка эликсира: 🧪 Бинты (+30% ❤️) — 5 💰."""
    hp = it.get("heal_percent") or 30
    return f"🧪 {it['name']} (+{hp}% ❤️) — {it['price']} 💰"


def _item_line(it: dict) -> str:
    """Строка предмета: Название — цена 💰."""
    return f"{it['name']} — {it['price']} 💰"


def _main_menu_text(credits: int) -> str:
    return (
        "🛒 <b>Магазин</b>\n\n"
        f"Ваши кредиты: {credits}\n\n"
        "Выберите категорию:"
    )


def _category_level_text(
    items: list[dict],
    credits: int,
    category_label: str,
    level: int,
    is_elixirs: bool = False,
) -> str:
    lines = [
        f"Ваши кредиты: {credits}\n",
        f"--- [ {category_label}: УРОВЕНЬ {level} ] ---\n" if not is_elixirs else f"--- [ {category_label} ] ---\n",
    ]
    if is_elixirs:
        for it in items:
            lines.append(_elixir_line(it))
    else:
        if not items:
            lines.append("Нет предметов для этого уровня.")
        else:
            for it in items:
                lines.append(_item_line(it))
    return "\n".join(lines)


def _elixirs_text(items: list[dict], credits: int) -> str:
    lines = [
        "🛒 <b>Магазин</b>\n",
        f"Ваши кредиты: {credits}\n",
        "--- [ 🧪 ЭЛИКСИРЫ ] ---\n",
    ]
    for it in items:
        lines.append(_elixir_line(it))
    return "\n".join(lines)


def _parse_shop_context_from_text(text: str | None) -> tuple[str | None, int | None]:
    """Из текста сообщения определить контекст: (category, level) или (None, None) для главного меню."""
    if not text:
        return None, None
    m = re.search(r"ОРУЖИЕ: УРОВЕНЬ\s*(\d+)", text, re.IGNORECASE)
    if m:
        return "weapons", int(m.group(1))
    m = re.search(r"ОДЕЖДА: УРОВЕНЬ\s*(\d+)", text, re.IGNORECASE)
    if m:
        return "armor", int(m.group(1))
    if "ЭЛИКСИРЫ" in text.upper():
        return "elixirs", None
    return None, None


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
    credits = stats.get("credits", 0)
    await message.answer(
        _main_menu_text(credits),
        reply_markup=shop_main_menu_keyboard(),
        parse_mode="HTML",
    )


@router.callback_query(F.data == "shop_cat:main")
async def shop_cat_main(callback: CallbackQuery) -> None:
    """Возврат в главное меню магазина."""
    player = await db.get_player_by_telegram_id(callback.from_user.id if callback.from_user else 0)
    if not player:
        await callback.answer("Сначала /start")
        return
    stats = await db.get_combat_stats(player["id"])
    credits = stats.get("credits", 0)
    await callback.message.edit_text(
        _main_menu_text(credits),
        reply_markup=shop_main_menu_keyboard(),
        parse_mode="HTML",
    )
    await callback.answer()


@router.callback_query(F.data.startswith("shop_cat:weapons:lvl:"))
async def shop_cat_weapons(callback: CallbackQuery) -> None:
    player = await db.get_player_by_telegram_id(callback.from_user.id if callback.from_user else 0)
    if not player:
        await callback.answer("Сначала /start")
        return
    if await db.has_active_fight(player["id"]):
        await callback.answer("🛑 Вы в бою!", show_alert=True)
        return
    try:
        level = int(callback.data.split(":")[-1])
    except (ValueError, IndexError):
        level = 1
    level = max(1, min(level, SHOP_MAX_LEVEL))
    all_items = await db.get_shop_items()
    items = db.get_shop_items_by_category(all_items, "weapons")
    items_level = [i for i in items if (i.get("min_level") or 1) == level]
    stats = await db.get_combat_stats(player["id"])
    credits = stats.get("credits", 0)
    text = _category_level_text(items_level, credits, "⚔️ ОРУЖИЕ", level, is_elixirs=False)
    text = "🛒 <b>Магазин</b>\n\n" + text
    kb = shop_category_level_keyboard(items_level, "weapons", level, SHOP_MAX_LEVEL)
    await callback.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data.startswith("shop_cat:armor:lvl:"))
async def shop_cat_armor(callback: CallbackQuery) -> None:
    player = await db.get_player_by_telegram_id(callback.from_user.id if callback.from_user else 0)
    if not player:
        await callback.answer("Сначала /start")
        return
    if await db.has_active_fight(player["id"]):
        await callback.answer("🛑 Вы в бою!", show_alert=True)
        return
    try:
        level = int(callback.data.split(":")[-1])
    except (ValueError, IndexError):
        level = 1
    level = max(1, min(level, SHOP_MAX_LEVEL))
    all_items = await db.get_shop_items()
    items = db.get_shop_items_by_category(all_items, "armor")
    items_level = [i for i in items if (i.get("min_level") or 1) == level]
    stats = await db.get_combat_stats(player["id"])
    credits = stats.get("credits", 0)
    text = _category_level_text(items_level, credits, "🛡️ ОДЕЖДА", level, is_elixirs=False)
    text = "🛒 <b>Магазин</b>\n\n" + text
    kb = shop_category_level_keyboard(items_level, "armor", level, SHOP_MAX_LEVEL)
    await callback.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data == "shop_cat:elixirs")
async def shop_cat_elixirs(callback: CallbackQuery) -> None:
    player = await db.get_player_by_telegram_id(callback.from_user.id if callback.from_user else 0)
    if not player:
        await callback.answer("Сначала /start")
        return
    if await db.has_active_fight(player["id"]):
        await callback.answer("🛑 Вы в бою!", show_alert=True)
        return
    all_items = await db.get_shop_items()
    items = db.get_shop_items_by_category(all_items, "elixirs")
    stats = await db.get_combat_stats(player["id"])
    credits = stats.get("credits", 0)
    text = _elixirs_text(items, credits)
    kb = shop_elixirs_keyboard(items)
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
        # Обновить текущий экран магазина (главное меню или категория)
        cat, lvl = _parse_shop_context_from_text(callback.message.text)
        stats = await db.get_combat_stats(player["id"])
        credits = stats.get("credits", 0)
        if cat is None:
            await callback.message.edit_text(
                _main_menu_text(credits) + "\n\n✅ " + msg,
                reply_markup=shop_main_menu_keyboard(),
                parse_mode="HTML",
            )
        elif cat == "elixirs":
            all_items = await db.get_shop_items()
            items = db.get_shop_items_by_category(all_items, "elixirs")
            await callback.message.edit_text(
                _elixirs_text(items, credits) + "\n\n✅ " + msg,
                reply_markup=shop_elixirs_keyboard(items),
                parse_mode="HTML",
            )
        else:
            level = lvl or 1
            level = max(1, min(level, SHOP_MAX_LEVEL))
            all_items = await db.get_shop_items()
            items = db.get_shop_items_by_category(all_items, cat)
            items_level = [i for i in items if (i.get("min_level") or 1) == level]
            label = "⚔️ ОРУЖИЕ" if cat == "weapons" else "🛡️ ОДЕЖДА"
            text = _category_level_text(items_level, credits, label, level, is_elixirs=False)
            text = "🛒 <b>Магазин</b>\n\n" + text + "\n\n✅ " + msg
            kb = shop_category_level_keyboard(items_level, cat, level, SHOP_MAX_LEVEL)
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
