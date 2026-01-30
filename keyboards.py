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
        KeyboardButton(text="⚔ Бой (манекен)"),
    )
    builder.row(
        KeyboardButton(text="🎒 Инвентарь"),
        KeyboardButton(text="🛒 Магазин"),
    )
    # Добавили кнопку Топ игроков рядом с Ареной
    builder.row(
        KeyboardButton(text="🏟 Арена (PvP)"),
        KeyboardButton(text="🏆 Топ игроков")
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


# ----- Battle (PvE) -----
def battle_pve_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="⚔ Ударить манекен", callback_data="pve_hit"))
    return builder.as_markup()


# ----- Arena -----
def arena_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="🔍 Найти соперника", callback_data="arena_find"))
    builder.row(InlineKeyboardButton(text="❌ Выйти из очереди", callback_data="arena_leave"))
    return builder.as_markup()


# Zones: 1=голова, 2=корпус, 3=ноги. Callback move_A_B = attack zone A, block zone B
def arena_move_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    zones = [(1, "голова"), (2, "корпус"), (3, "ноги")]
    for atk_z, atk_name in zones:
        for blk_z, blk_name in zones:
            builder.row(
                InlineKeyboardButton(
                    text=f"Удар: {atk_name} | Блок: {blk_name}",
                    callback_data=f"move_{atk_z}_{blk_z}",
                )
            )
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