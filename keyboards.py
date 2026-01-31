"""
Inline and reply keyboards for the bot.
"""
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder

# ----- Main menu -----
def main_menu() -> ReplyKeyboardMarkup:
    builder = ReplyKeyboardBuilder()
    builder.row(
        KeyboardButton(text="📋 Профиль"),
        KeyboardButton(text="🏟 Арена (PvP)"),
    )
    builder.row(
        KeyboardButton(text="👥 Бой с тенью"),
        KeyboardButton(text="🎒 Инвентарь"),
    )
    builder.row(
        KeyboardButton(text="🛒 Магазин"),
        KeyboardButton(text="🏆 Топ игроков"),
    )
    builder.row(KeyboardButton(text="🆘 Помощь"))
    return builder.as_markup(resize_keyboard=True)


# ----- Profile: stat upgrade -----
def profile_upgrade_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="Сила [+]", callback_data="stat_strength"),
        InlineKeyboardButton(text="Ловкость [+]", callback_data="stat_agility"),
    )
    builder.row(
        InlineKeyboardButton(text="Интуиция [+]", callback_data="stat_intuition"),
        InlineKeyboardButton(text="Выносливость [+]", callback_data="stat_stamina"),
    )
    return builder.as_markup()


def profile_upgrade_keyboard_with_top() -> InlineKeyboardMarkup:
    """Профиль + кнопка ТОП-10 (callback show_top)."""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="Сила [+]", callback_data="stat_strength"),
        InlineKeyboardButton(text="Ловкость [+]", callback_data="stat_agility"),
    )
    builder.row(
        InlineKeyboardButton(text="Интуиция [+]", callback_data="stat_intuition"),
        InlineKeyboardButton(text="Выносливость [+]", callback_data="stat_stamina"),
    )
    builder.row(InlineKeyboardButton(text="🏆 ТОП-10", callback_data="show_top"))
    return builder.as_markup()


# Зоны: 1=Голова, 2=Корпус, 3=Ноги
ZONE_NAMES = {1: "Голова", 2: "Корпус", 3: "Ноги"}


def _zone_btn(label: str, prefix: str, zone: int, selected: bool) -> InlineKeyboardButton:
    text = f"✅ {label}" if selected else label
    return InlineKeyboardButton(text=text, callback_data=f"{prefix}_{zone}")


# ----- Шахматка: два столбца (Атака | Защита), зоны 1–3. bandage_remaining — остаток использований бинтов в бою (0–2).
def arena_move_keyboard(
    selected_atk: int | None = None,
    selected_def: int | None = None,
    bandage_remaining: int | None = None,
) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    # Ряд: Атака — три зоны
    row_atk = [
        _zone_btn("Атака: " + ZONE_NAMES[1], "move_atk", 1, selected_atk == 1),
        _zone_btn("Атака: " + ZONE_NAMES[2], "move_atk", 2, selected_atk == 2),
        _zone_btn("Атака: " + ZONE_NAMES[3], "move_atk", 3, selected_atk == 3),
    ]
    builder.row(*row_atk)
    # Ряд: Защита — три зоны
    row_def = [
        _zone_btn("Защита: " + ZONE_NAMES[1], "move_def", 1, selected_def == 1),
        _zone_btn("Защита: " + ZONE_NAMES[2], "move_def", 2, selected_def == 2),
        _zone_btn("Защита: " + ZONE_NAMES[3], "move_def", 3, selected_def == 3),
    ]
    builder.row(*row_def)
    if selected_atk is not None and selected_def is not None:
        builder.row(InlineKeyboardButton(text="⚔ ПОДТВЕРДИТЬ УДАР", callback_data="move_confirm"))
    heal_btn_text = "🧪 Хил (2 шт. осталось)"
    if bandage_remaining is not None:
        heal_btn_text = f"🧪 Хил ({bandage_remaining} шт. осталось)" if bandage_remaining > 0 else "🧪 Хил (0 шт.)"
    builder.row(
        InlineKeyboardButton(text="🎲 Автобой", callback_data="move_auto"),
        InlineKeyboardButton(text=heal_btn_text, callback_data="move_heal"),
    )
    builder.row(InlineKeyboardButton(text="🏳 Сдаться", callback_data="surrender"))
    return builder.as_markup()


def shadow_move_keyboard(
    selected_atk: int | None = None,
    selected_def: int | None = None,
    bandage_remaining: int | None = None,
) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    row_atk = [
        _zone_btn("Атака: " + ZONE_NAMES[1], "shadow_atk", 1, selected_atk == 1),
        _zone_btn("Атака: " + ZONE_NAMES[2], "shadow_atk", 2, selected_atk == 2),
        _zone_btn("Атака: " + ZONE_NAMES[3], "shadow_atk", 3, selected_atk == 3),
    ]
    builder.row(*row_atk)
    row_def = [
        _zone_btn("Защита: " + ZONE_NAMES[1], "shadow_def", 1, selected_def == 1),
        _zone_btn("Защита: " + ZONE_NAMES[2], "shadow_def", 2, selected_def == 2),
        _zone_btn("Защита: " + ZONE_NAMES[3], "shadow_def", 3, selected_def == 3),
    ]
    builder.row(*row_def)
    if selected_atk is not None and selected_def is not None:
        builder.row(InlineKeyboardButton(text="⚔ ПОДТВЕРДИТЬ УДАР", callback_data="shadow_confirm"))
    heal_btn_text = "🧪 Хил (2 шт. осталось)"
    if bandage_remaining is not None:
        heal_btn_text = f"🧪 Хил ({bandage_remaining} шт. осталось)" if bandage_remaining > 0 else "🧪 Хил (0 шт.)"
    builder.row(
        InlineKeyboardButton(text="🎲 Автобой", callback_data="shadow_auto"),
        InlineKeyboardButton(text=heal_btn_text, callback_data="shadow_heal"),
    )
    return builder.as_markup()


# ----- Arena -----
def arena_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="🔍 Найти соперника", callback_data="arena_find"))
    builder.row(InlineKeyboardButton(text="❌ Отменить поиск", callback_data="arena_leave"))
    return builder.as_markup()


# ----- Inventory: list items, equip/unequip -----
def inventory_item_keyboard(inv_id: int, is_equipped: bool) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    if is_equipped:
        builder.row(InlineKeyboardButton(text="Снять", callback_data=f"inv_unequip_{inv_id}"))
    else:
        builder.row(InlineKeyboardButton(text="Надеть", callback_data=f"inv_equip_{inv_id}"))
    return builder.as_markup()


def inventory_list_keyboard(items: list[dict]) -> InlineKeyboardMarkup:
    """One row per item: name + [Надеть] or [Снять]."""
    builder = InlineKeyboardBuilder()
    for inv in items:
        label = "Снять" if inv["is_equipped"] else "Надеть"
        cb = f"inv_unequip_{inv['id']}" if inv["is_equipped"] else f"inv_equip_{inv['id']}"
        builder.row(
            InlineKeyboardButton(text=f"{inv['name']} — {label}", callback_data=cb),
        )
    return builder.as_markup()


def inventory_back_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="« Назад к списку", callback_data="inv_back"))
    return builder.as_markup()


# ----- Shop: каталог по категориям (Оружие, Одежда, Эликсиры) -----
def shop_buy_keyboard(item_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="Купить", callback_data=f"shop_buy_{item_id}"))
    return builder.as_markup()


def shop_sell_keyboard(inv_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="Продать (50%)", callback_data=f"shop_sell_{inv_id}"))
    return builder.as_markup()


def shop_main_menu_keyboard() -> InlineKeyboardMarkup:
    """Главное меню магазина: Оружие, Одежда, Эликсиры."""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="⚔️ Оружие", callback_data="shop_cat:weapons:lvl:1"),
        InlineKeyboardButton(text="🛡️ Одежда", callback_data="shop_cat:armor:lvl:1"),
    )
    builder.row(InlineKeyboardButton(text="🧪 Эликсиры", callback_data="shop_cat:elixirs"))
    return builder.as_markup()


def shop_category_level_keyboard(
    items_page: list[dict],
    category: str,
    level: int,
    max_level: int = 5,
) -> InlineKeyboardMarkup:
    """Клавиатура категории (оружие/одежда): Купить по предметам + ⬅️ Ур. n-1 / Ур. n+1 ➡️ + 🔙 Назад."""
    builder = InlineKeyboardBuilder()
    for it in items_page:
        builder.row(
            InlineKeyboardButton(text=f"Купить: {it['name']}", callback_data=f"shop_buy_{it['id']}"),
        )
    row_nav = []
    if level > 1:
        row_nav.append(InlineKeyboardButton(text=f"⬅️ Ур. {level - 1}", callback_data=f"shop_cat:{category}:lvl:{level - 1}"))
    if level < max_level:
        row_nav.append(InlineKeyboardButton(text=f"Ур. {level + 1} ➡️", callback_data=f"shop_cat:{category}:lvl:{level + 1}"))
    if row_nav:
        builder.row(*row_nav)
    builder.row(InlineKeyboardButton(text="🔙 Назад в меню", callback_data="shop_cat:main"))
    return builder.as_markup()


def shop_elixirs_keyboard(items: list[dict]) -> InlineKeyboardMarkup:
    """Эликсиры: Купить по каждому + 🔙 Назад."""
    builder = InlineKeyboardBuilder()
    for it in items:
        builder.row(
            InlineKeyboardButton(text=f"Купить: {it['name']}", callback_data=f"shop_buy_{it['id']}"),
        )
    builder.row(InlineKeyboardButton(text="🔙 Назад в меню", callback_data="shop_cat:main"))
    return builder.as_markup()


def shop_list_keyboard(items: list[dict], player_class: str | None = None) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for it in items:
        name = f"🧪 {it['name']}" if it.get("slot") == "potion" else it["name"]
        min_lvl = it.get("min_level", 1) or 1
        item_class = (it.get("class_type") or "all").lower()
        wrong_class = ""
        if item_class != "all" and player_class and item_class != player_class:
            wrong_class = " | ⚠️ Не для вашего класса"
        builder.row(
            InlineKeyboardButton(
                text=f"{name} — 💰 {it['price']} кр. | 🎖 Lvl: {min_lvl}{wrong_class}",
                callback_data=f"shop_item_{it['id']}",
            )
        )
    return builder.as_markup()