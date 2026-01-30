"""
PvE: fight dummy, get XP, 1–3 credits, 20% drop "Ржавый нож".
"""
import random
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command

from keyboards import battle_pve_keyboard
from services.game_math import BattleMath
from database.db import db

router = Router(name="battle")

DUMMY_STATS = {
    "strength": 3,
    "agility": 3,
    "intuition": 3,
    "stamina": 3,
    "hp": 15,
    "weapon_min": 1,
    "weapon_max": 2,
}
RUSTY_KNIFE_ITEM_NAME = "Ржавый нож"
DROP_CHANCE = 0.20
XP_REWARD = 5
CREDITS_MIN, CREDITS_MAX = 1, 3


@router.message(F.text == "⚔ Бой (манекен)")
@router.message(Command("battle"))
async def battle_pve_menu(message: Message) -> None:
    
    player = await db.get_player_by_telegram_id(message.from_user.id if message.from_user else 0)
    if not player:
        await message.answer("Сначала /start")
        return
    stats = await db.get_combat_stats(player["id"])
    if not stats:
        await message.answer("Ошибка загрузки статов.")
        return
    wmin, wmax = stats.get("weapon_min", 1), stats.get("weapon_max", 2)
    if wmax < wmin:
        wmax = wmin
    await message.answer(
        "Манекен ждёт. Нанеси удар!\n"
        f"Ваши статы: HP {stats['hp']}, урон оружия {wmin}-{wmax}.",
        reply_markup=battle_pve_keyboard(),
    )


@router.callback_query(F.data == "pve_hit")
async def pve_hit(callback: CallbackQuery) -> None:

    player = await db.get_player_by_telegram_id(callback.from_user.id if callback.from_user else 0)
    if not player:
        await callback.answer("Сначала /start")
        return
    stats = await db.get_combat_stats(player["id"])
    if not stats:
        await callback.answer("Ошибка статов")
        return
    wmin = stats.get("weapon_min", 1)
    wmax = max(stats.get("weapon_max", 1), wmin)
    damage = BattleMath.base_damage(wmin, wmax, stats["strength"])
    credits = random.randint(CREDITS_MIN, CREDITS_MAX)
    await db.add_credits(player["id"], credits)
    await db.add_experience(player["id"], XP_REWARD)
    drop_text = ""
    if random.random() < DROP_CHANCE:
        item = await db.get_item_by_name(RUSTY_KNIFE_ITEM_NAME)
        if item:
            await db.add_item_to_inventory(player["id"], item["id"], False)
            drop_text = f"\n🎁 Дроп: {RUSTY_KNIFE_ITEM_NAME}!"
    text = (
        f"Вы нанесли манекену {damage} урона.\n"
        f"+{XP_REWARD} XP, +{credits} кр.{drop_text}\n\n"
        "Можно ударить снова."
    )
    await callback.message.edit_text(text, reply_markup=battle_pve_keyboard())
    await callback.answer()
