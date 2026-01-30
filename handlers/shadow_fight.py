"""
Бой с тенью: шахматка (Атака/Защита), лог с чёрным юмором, восстановление HP после боя.
"""
import random
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
from aiogram.utils.keyboard import InlineKeyboardBuilder

from keyboards import shadow_move_keyboard, ZONE_NAMES
from services.battle_phrases import get_victory_phrase, get_defeat_phrase
from database.db import db

router = Router(name="shadow_fight")

_shadow_selection: dict[int, dict] = {}  # player_id -> {"atk": int|None, "def": int|None}


SHADOW_MAX_HP = 40  # фиксированное HP тени для честного теста

def draw_hp_bar(current: int, max_hp: int = 40, length: int = 8) -> str:
    if current <= 0:
        return "💀 (0)"
    percent = max(0, min(1, current / max_hp))
    filled = int(length * percent)
    empty = length - filled
    bar = "🟩" * filled if percent > 0.6 else "🟨" * filled if percent > 0.3 else "🟥" * filled
    return f"{bar}{'⬜' * empty} ({current})"


def _shadow_kb(player_id: int):
    sel = _shadow_selection.get(player_id, {})
    return shadow_move_keyboard(sel.get("atk"), sel.get("def"))


@router.message(F.text == "👥 Бой с тенью")
@router.message(Command("shadow"))
async def shadow_menu(message: Message) -> None:
    player = await db.get_player_by_telegram_id(message.from_user.id if message.from_user else 0)
    if not player:
        await message.answer("Сначала /start")
        return
    if await db.has_trauma(player["id"]):
        await message.answer(
            "🛑 <b>Вы ранены!</b>\n\nПодождите или выпейте эликсир (Инвентарь → Зелья → Выпить).",
            parse_mode="HTML",
        )
        return

    active = await db.get_active_shadow_fight(player["id"])
    if active:
        txt = (
            f"👥 <b>Бой с тенью</b>\n\n"
            f"👤 Вы: {draw_hp_bar(active['player_hp'])}\n"
            f"👻 Тень: {draw_hp_bar(active['shadow_hp'], SHADOW_MAX_HP)}\n\n"
            "👇 Выберите зону атаки и защиты:"
        )
        try:
            await message.delete()
        except Exception:
            pass
        await message.answer(txt, reply_markup=_shadow_kb(player["id"]), parse_mode="HTML")
        return

    txt = (
        "👥 <b>Бой с тенью</b>\n\n"
        "Тень копирует ваши статы (урон тени −20%). HP тени = 20.\n"
        "Победа: +20 кр., +50 опыта. Поражение: +6 кр., +25 опыта. HP восстанавливается после боя.\n\n"
        "Нажмите кнопку ниже, чтобы начать."
    )
    await message.answer(txt, reply_markup=shadow_start_keyboard(), parse_mode="HTML")


def shadow_start_keyboard():
    builder = InlineKeyboardBuilder()
    builder.button(text="⚔ Начать бой с тенью", callback_data="shadow_start")
    return builder.as_markup()


@router.callback_query(F.data == "shadow_start")
async def shadow_start(callback: CallbackQuery) -> None:
    player = await db.get_player_by_telegram_id(callback.from_user.id if callback.from_user else 0)
    if not player:
        await callback.answer("Сначала /start")
        return
    if await db.has_trauma(player["id"]):
        await callback.answer("🛑 Вы ранены! Подождите или выпейте эликсир.", show_alert=True)
        return
    active = await db.get_active_shadow_fight(player["id"])
    if active:
        await callback.answer("У вас уже есть активный бой с тенью.")
        return
    fight = await db.start_shadow_fight(player["id"])
    if not fight:
        await callback.answer("Ошибка создания боя")
        return
    txt = (
        f"⚔️ <b>БОЙ</b>\nБой с тенью начался!\n\n"
        f"👤 Вы: {draw_hp_bar(fight['player_hp'])}\n"
        f"👻 Тень: {draw_hp_bar(fight['shadow_hp'], SHADOW_MAX_HP)}\n\n"
        "👇 Выберите зону атаки и защиты:"
    )
    await callback.message.edit_text(txt, reply_markup=_shadow_kb(player["id"]), parse_mode="HTML")
    await callback.answer("Бой начат!")


@router.callback_query(F.data.startswith("shadow_atk_"))
@router.callback_query(F.data.startswith("shadow_def_"))
async def shadow_select_zone(callback: CallbackQuery) -> None:
    player = await db.get_player_by_telegram_id(callback.from_user.id if callback.from_user else 0)
    if not player:
        return
    fight = await db.get_active_shadow_fight(player["id"])
    if not fight:
        await callback.answer("Нет активного боя с тенью.")
        return

    _shadow_selection.setdefault(player["id"], {"atk": None, "def": None})
    parts = callback.data.split("_")
    zone = int(parts[-1])
    if callback.data.startswith("shadow_atk_"):
        _shadow_selection[player["id"]]["atk"] = zone
    else:
        _shadow_selection[player["id"]]["def"] = zone

    sel = _shadow_selection[player["id"]]
    txt = (
        f"👥 <b>Бой с тенью</b>\n\n"
        f"👤 Вы: {draw_hp_bar(fight['player_hp'])}\n"
        f"👻 Тень: {draw_hp_bar(fight['shadow_hp'], SHADOW_MAX_HP)}\n\n"
        f"Атака: {ZONE_NAMES.get(sel['atk'], '—')} | Защита: {ZONE_NAMES.get(sel['def'], '—')}\n\n"
        "👇 Подтвердите удар или нажмите «Автобой»:"
    )
    await callback.message.edit_text(txt, reply_markup=_shadow_kb(player["id"]), parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data == "shadow_heal")
async def shadow_heal(callback: CallbackQuery) -> None:
    """Free Action: зелье 1 раз за бой, не тратит ход. Обновляем HP и оставляем клавиатуру."""
    player = await db.get_player_by_telegram_id(callback.from_user.id if callback.from_user else 0)
    if not player:
        return
    fight = await db.get_active_shadow_fight(player["id"])
    if not fight:
        await callback.answer("Нет активного боя с тенью.")
        return
    ok, new_hp, msg = await db.use_potion_shadow(fight["id"], player["id"])
    if not ok:
        await callback.answer(msg, show_alert=True)
        return
    await callback.answer(msg)
    fight = await db.get_active_shadow_fight(player["id"])
    stats = await db.get_combat_stats(player["id"])
    max_hp = stats.get("max_hp", 40)
    txt = (
        f"👥 <b>Бой с тенью</b>\n\n"
        f"🧪 {msg}\n\n"
        f"👤 Вы: {draw_hp_bar(new_hp, max_hp)}\n"
        f"👻 Тень: {draw_hp_bar(fight['shadow_hp'], SHADOW_MAX_HP)}\n\n"
        "👇 Выберите зону атаки и защиты (ход не потрачен):"
    )
    try:
        await callback.message.edit_text(
            txt,
            reply_markup=_shadow_kb(player["id"]),
            parse_mode="HTML",
        )
    except Exception:
        await callback.message.answer(txt, reply_markup=_shadow_kb(player["id"]), parse_mode="HTML")


@router.callback_query(F.data == "shadow_confirm")
@router.callback_query(F.data == "shadow_auto")
async def shadow_confirm_move(callback: CallbackQuery) -> None:
    player = await db.get_player_by_telegram_id(callback.from_user.id if callback.from_user else 0)
    if not player:
        return
    fight = await db.get_active_shadow_fight(player["id"])
    if not fight:
        await callback.answer("Нет активного боя с тенью.")
        return

    if callback.data == "shadow_auto":
        atk, blk = random.randint(1, 3), random.randint(1, 3)
    else:
        sel = _shadow_selection.get(player["id"], {})
        atk, blk = sel.get("atk"), sel.get("def")
        if atk is None or blk is None:
            await callback.answer("Выберите зону атаки и зону защиты.", show_alert=True)
            return

    updated, stats, log_lines, player_won, leveled_up = await db.process_shadow_turn(fight["id"], atk, blk)
    _shadow_selection.pop(player["id"], None)

    if not updated:
        await callback.answer("Бой уже завершён.")
        return

    log_str = "\n".join(log_lines[-4:])
    max_hp = stats.get("max_hp", 40)
    bar_player = draw_hp_bar(updated["player_hp"], max_hp)
    bar_shadow = draw_hp_bar(updated["shadow_hp"], SHADOW_MAX_HP)

    if updated["is_finished"]:
        lvl = stats.get("level", 1)
        xp_win, gold_win = 20 + lvl * 5, 10 + lvl * 2
        lvl_banner = "\n🎖 <b>УРОВЕНЬ ПОВЫШЕН!</b>" if leveled_up else ""
        if player_won:
            result = f"🏆 <b>ПОБЕДА!</b>\n{get_victory_phrase()}\n💰 +{gold_win} кр. | 📊 +{xp_win} опыта{lvl_banner}\n👉 /shadow"
        else:
            result = f"💀 <b>ПОРАЖЕНИЕ.</b>\n{get_defeat_phrase()}\n💰 +{max(1, int(gold_win*0.3))} кр. | 📊 +{max(1, int(xp_win*0.5))} опыта{lvl_banner}\n👉 /shadow"
        try:
            await callback.message.edit_text(
                f"👥 <b>Раунд {updated['round']}</b>\n{log_str}\n\n"
                f"👤 Вы: {bar_player}\n👻 Тень: {bar_shadow}\n\n{result}",
                reply_markup=None,
                parse_mode="HTML",
            )
        except Exception:
            await callback.message.answer(
                f"👥 <b>Раунд {updated['round']}</b>\n{log_str}\n\n"
                f"👤 Вы: {bar_player}\n👻 Тень: {bar_shadow}\n\n{result}",
                parse_mode="HTML",
            )
        await callback.answer("Бой завершён" if player_won else "Вы проиграли")
        return

    txt = (
        f"👥 <b>Раунд {updated['round']}</b>\n{log_str}\n\n"
        f"👤 Вы: {bar_player}\n👻 Тень: {bar_shadow}\n\n👇 Ваш ход:"
    )
    try:
        await callback.message.edit_text(txt, reply_markup=_shadow_kb(player["id"]), parse_mode="HTML")
    except Exception:
        await callback.message.answer(txt, reply_markup=_shadow_kb(player["id"]), parse_mode="HTML")
    await callback.answer("Ход принят")
