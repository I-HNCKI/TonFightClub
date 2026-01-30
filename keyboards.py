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


# Зоны: 1=Голова, 2=Корпус, 3=Ноги
ZONE_NAMES = {1: "Голова", 2: "Корпус", 3: "Ноги"}


def _zone_btn(label: str, prefix: str, zone: int, selected: bool) -> InlineKeyboardButton:
    text = f"✅ {label}" if selected else label
    return InlineKeyboardButton(text=text, callback_data=f"{prefix}_{zone}")


# ----- Шахматка: два столбца (Атака | Защита), зоны 1–3. Кнопка "ПОДТВЕРДИТЬ УДАР" только при выборе атаки и защиты.
def arena_move_keyboard(selected_atk: int | None = None, selected_def: int | None = None) -> InlineKeyboardMarkup:
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
    builder.row(
        InlineKeyboardButton(text="🎲 Автобой", callback_data="move_auto"),
        InlineKeyboardButton(text="🧪 Хил", callback_data="move_heal"),
    )
    builder.row(InlineKeyboardButton(text="🏳 Сдаться", callback_data="surrender"))
    return builder.as_markup()


def shadow_move_keyboard(selected_atk: int | None = None, selected_def: int | None = None) -> InlineKeyboardMarkup:
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
    builder.row(
        InlineKeyboardButton(text="🎲 Автобой", callback_data="shadow_auto"),
        InlineKeyboardButton(text="🧪 Хил", callback_data="shadow_heal"),
    )
    return builder.as_markup()


# ----- Arena -----
def arena_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="🔍 Найти соперника", callback_data="arena_find"))
    builder.row(InlineKeyboardButton(text="❌ Выйти из очереди", callback_data="arena_leave"))
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


# ----- Shop -----
def shop_buy_keyboard(item_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="Купить", callback_data=f"shop_buy_{item_id}"))
    return builder.as_markup()


def shop_sell_keyboard(inv_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="Продать (50%)", callback_data=f"shop_sell_{inv_id}"))
    return builder.as_markup()


def shop_list_keyboard(items: list[dict]) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for it in items:
        builder.row(
            InlineKeyboardButton(
                text=f"{it['name']} — {it['price']} кр.",
                callback_data=f"shop_item_{it['id']}",
            )
        )
    return builder.as_markup()