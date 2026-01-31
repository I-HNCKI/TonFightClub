"""
PvP Arena: шахматка (Атака/Защита), лог с чёрным юмором, травмы (1 HP/мин), финальные фразы.
"""
import random
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command

from keyboards import arena_keyboard, arena_move_keyboard, ZONE_NAMES
from services.game_math import BattleMath, CombatStats
from services.battle_phrases import get_victory_phrase, get_defeat_phrase
from database.db import Database
from database.db import db

router = Router(name="arena")

# Состояние выбора зон: (player_id, battle_id) -> {"atk": int|None, "def": int|None}
_arena_selection: dict[tuple[int, int], dict] = {}


def draw_hp_bar(current: int, max_hp: int = 50, length: int = 8) -> str:
    if current <= 0:
        return "💀 (0)"
    percent = max(0, min(1, current / max_hp)) if max_hp else 0
    filled = int(length * percent)
    empty = length - filled
    bar = "🟩" * filled if percent > 0.6 else "🟨" * filled if percent > 0.3 else "🟥" * filled
    return f"{bar}{'⬜' * empty} ({current})"


async def get_telegram_id_by_player_id(db_inst: Database, player_id: int) -> int | None:
    async with db_inst.pool.acquire() as conn:
        row = await conn.fetchrow("SELECT telegram_id FROM players WHERE id = $1", player_id)
        return row["telegram_id"] if row else None


BANDAGE_LIMIT = 2


def _arena_kb(player_id: int, battle_id: int, battle: dict | None = None, bandage_remaining: int | None = None):
    sel = _arena_selection.get((player_id, battle_id), {})
    if bandage_remaining is None and battle:
        is_p1 = battle["player1_id"] == player_id
        used = battle.get("p1_bandage_uses" if is_p1 else "p2_bandage_uses", 0) or 0
        bandage_remaining = max(0, BANDAGE_LIMIT - used)
    return arena_move_keyboard(sel.get("atk"), sel.get("def"), bandage_remaining)


@router.message(F.text == "🏟 Арена (PvP)")
@router.message(Command("arena"))
async def arena_menu(message: Message) -> None:
    await db.close_stale_battles(15)
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

    battle = await db.get_active_battle_for_player(player["id"])
    if battle:
        is_p1 = battle["player1_id"] == player["id"]
        my_hp = battle["player1_hp"] if is_p1 else battle["player2_hp"]
        opp_hp = battle["player2_hp"] if is_p1 else battle["player1_hp"]
        opp_name = (battle["p2_name"] if is_p1 else battle["p1_name"]) or "Соперник"
        s = await db.get_combat_stats(player["id"], for_arena=True)
        max_hp = s.get("max_hp", 50)

        txt = (
            f"⚔ <b>Ваш бой продолжается!</b>\n\n"
            f"👤 Вы: {draw_hp_bar(my_hp, max_hp)}\n"
            f"👤 {opp_name}: {draw_hp_bar(opp_hp)}\n\n"
            "👇 Выберите зону атаки и защиты, затем подтвердите удар:"
        )
        try:
            await message.delete()
        except Exception:
            pass
        new_msg = await message.answer(txt, reply_markup=_arena_kb(player["id"], battle["id"], battle=battle), parse_mode="HTML")
        await db.set_battle_message_id(battle["id"], player["id"], new_msg.message_id)
        return

    await message.answer(
        "🏟 <b>Арена PvP</b>\n\nНажмите «Найти соперника».",
        reply_markup=arena_keyboard(),
        parse_mode="HTML",
    )


@router.callback_query(F.data == "arena_find")
async def arena_find(callback: CallbackQuery) -> None:
    await db.close_stale_battles(15)
    player = await db.get_player_by_telegram_id(callback.from_user.id if callback.from_user else 0)
    if not player:
        return
    if await db.has_trauma(player["id"]):
        await callback.answer("🛑 Вы ранены! Подождите или выпейте эликсир.", show_alert=True)
        return

    status, battle_id, msg = await db.arena_join_queue(player["id"], stake=10)

    if status == "no_credits":
        await callback.answer(msg, show_alert=True)
        return
    if status == "no_match":
        await callback.answer(msg, show_alert=True)
        return

    if status == "waiting":
        await callback.message.edit_text(
            "⏳ <b>Поиск соперника...</b>\nСтавка: 10 кр. Ожидайте.",
            reply_markup=arena_keyboard(),
            parse_mode="HTML",
        )
        await callback.answer()
        return

    if status == "matched" and battle_id:
        battle = await db.get_battle(battle_id)
        p1_tg = await get_telegram_id_by_player_id(db, battle["player1_id"])
        p2_tg = await get_telegram_id_by_player_id(db, battle["player2_id"])
        stake = battle.get("stake") or 10
        s1 = await db.get_combat_stats(battle["player1_id"], for_arena=True)
        s2 = await db.get_combat_stats(battle["player2_id"], for_arena=True)
        max1, max2 = s1.get("max_hp", 50), s2.get("max_hp", 50)

        txt1 = (
            f"⚔ <b>БОЙ НАЧАЛСЯ!</b> (ставка {stake} кр.)\n\n"
            f"👤 Вы: {draw_hp_bar(battle['player1_hp'], max1)}\n"
            f"🆚 {battle['p2_name'] or 'Боец'}: {draw_hp_bar(battle['player2_hp'], max2)}\n\n"
            "👇 Выберите зону атаки и защиты:"
        )
        txt2 = (
            f"⚔️ <b>БОЙ</b>\nБой начался! (ставка {stake} кр.)\n\n"
            f"👤 Вы: {draw_hp_bar(battle['player2_hp'], max2)}\n"
            f"🆚 {battle['p1_name'] or 'Боец'}: {draw_hp_bar(battle['player1_hp'], max1)}\n\n"
            "👇 Выберите зону атаки и защиты:"
        )
        kb = arena_move_keyboard(None, None, BANDAGE_LIMIT)

        if p1_tg:
            m = await callback.bot.send_message(p1_tg, txt1, reply_markup=kb, parse_mode="HTML")
            await db.set_battle_message_id(battle_id, battle["player1_id"], m.message_id)
        if p2_tg:
            m = await callback.bot.send_message(p2_tg, txt2, reply_markup=kb, parse_mode="HTML")
            await db.set_battle_message_id(battle_id, battle["player2_id"], m.message_id)

        try:
            await callback.message.delete()
        except Exception:
            pass
    await callback.answer()


@router.callback_query(F.data == "arena_leave")
async def arena_cancel_search(callback: CallbackQuery) -> None:
    """Отмена поиска: только если игрок в очереди, не в бою. Возврат ставки 10 кр."""
    player = await db.get_player_by_telegram_id(callback.from_user.id if callback.from_user else 0)
    if not player:
        await callback.answer("Сначала /start")
        return
    if await db.get_active_battle_for_player(player["id"]):
        await callback.answer("Бой уже начался. Отмена невозможна.", show_alert=True)
        return
    ok, msg = await db.arena_leave_queue(player["id"], stake=10)
    if not ok:
        await callback.answer(msg, show_alert=True)
        return
    await callback.message.edit_text(
        f"✅ {msg}\n\n"
        "🏟 <b>Арена PvP</b>\n\nНажмите «Найти соперника».",
        reply_markup=arena_keyboard(),
        parse_mode="HTML",
    )
    await callback.answer(msg)


# Выбор зоны атаки/защиты (шахматка)
@router.callback_query(F.data.startswith("move_atk_"))
@router.callback_query(F.data.startswith("move_def_"))
async def arena_select_zone(callback: CallbackQuery) -> None:
    player = await db.get_player_by_telegram_id(callback.from_user.id if callback.from_user else 0)
    if not player:
        return
    battle = await db.get_active_battle_for_player(player["id"])
    if not battle:
        await callback.answer("Бой завершён.")
        return

    key = (player["id"], battle["id"])
    _arena_selection.setdefault(key, {"atk": None, "def": None})
    parts = callback.data.split("_")
    zone = int(parts[-1])
    if callback.data.startswith("move_atk_"):
        _arena_selection[key]["atk"] = zone
    else:
        _arena_selection[key]["def"] = zone

    is_p1 = battle["player1_id"] == player["id"]
    my_hp = battle["player1_hp"] if is_p1 else battle["player2_hp"]
    opp_hp = battle["player2_hp"] if is_p1 else battle["player1_hp"]
    opp_name = (battle["p2_name"] if is_p1 else battle["p1_name"]) or "Соперник"
    s = await db.get_combat_stats(player["id"], for_arena=True)
    max_hp = s.get("max_hp", 50)

    sel = _arena_selection[key]
    txt = (
        f"⚔ <b>Бой</b>\n\n"
        f"👤 Вы: {draw_hp_bar(my_hp, max_hp)}\n"
        f"👤 {opp_name}: {draw_hp_bar(opp_hp)}\n\n"
        f"Атака: {ZONE_NAMES.get(sel['atk'], '—')} | Защита: {ZONE_NAMES.get(sel['def'], '—')}\n\n"
        "👇 Выберите зоны и нажмите «ПОДТВЕРДИТЬ УДАР»:"
    )
    await callback.message.edit_text(txt, reply_markup=_arena_kb(player["id"], battle["id"], battle=battle), parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data == "move_heal")
async def arena_heal(callback: CallbackQuery) -> None:
    """Free Action: зелье не тратит ход, 1 раз за бой. Обновляем HP и оставляем клавиатуру выбора удара."""
    player = await db.get_player_by_telegram_id(callback.from_user.id if callback.from_user else 0)
    if not player:
        return
    battle = await db.get_active_battle_for_player(player["id"])
    if not battle:
        await callback.answer("Бой завершён.")
        return
    ok, msg = await db.make_heal_arena(battle["id"], player["id"])
    if not ok:
        await callback.answer(msg, show_alert=True)
        return
    await callback.answer(msg)
    battle = await db.get_battle(battle["id"])
    is_p1 = battle["player1_id"] == player["id"]
    my_hp = battle["player1_hp"] if is_p1 else battle["player2_hp"]
    opp_hp = battle["player2_hp"] if is_p1 else battle["player1_hp"]
    opp_name = (battle["p2_name"] if is_p1 else battle["p1_name"]) or "Соперник"
    s = await db.get_combat_stats(player["id"], for_arena=True)
    max_hp = s.get("max_hp", 40)
    txt = (
        f"⚔️ <b>Бой</b>\n\n"
        f"🧪 {msg}\n\n"
        f"👤 Вы: {draw_hp_bar(my_hp, max_hp)}\n"
        f"👤 {opp_name}: {draw_hp_bar(opp_hp)}\n\n"
        "👇 Выберите зону атаки и защиты (ход не потрачен):"
    )
    try:
        await callback.message.edit_text(
            txt,
            reply_markup=_arena_kb(player["id"], battle["id"], battle=battle),
            parse_mode="HTML",
        )
    except Exception:
        pass


@router.callback_query(F.data == "move_confirm")
@router.callback_query(F.data == "move_auto")
async def arena_confirm_move(callback: CallbackQuery) -> None:
    player = await db.get_player_by_telegram_id(callback.from_user.id if callback.from_user else 0)
    if not player:
        return
    battle = await db.get_active_battle_for_player(player["id"])
    if not battle:
        await callback.message.edit_text("❌ Бой завершён.", reply_markup=None)
        return

    key = (player["id"], battle["id"])
    sel = _arena_selection.get(key, {})

    if callback.data == "move_auto":
        atk, blk = random.randint(1, 3), random.randint(1, 3)
    else:
        atk, blk = sel.get("atk"), sel.get("def")
        if atk is None or blk is None:
            await callback.answer("Выберите зону атаки и зону защиты.", show_alert=True)
            return

    ok, msg = await db.make_move(battle["id"], player["id"], atk, blk)
    if not ok:
        await callback.answer(msg, show_alert=True)
        return

    _arena_selection.pop(key, None)
    await callback.answer("Ход принят")

    try:
        await callback.message.edit_text(
            f"⏳ <b>Ожидание противника...</b>\n\n"
            f"💥 Атака: {ZONE_NAMES.get(atk)}\n🛡 Защита: {ZONE_NAMES.get(blk)}",
            reply_markup=None,
            parse_mode="HTML",
        )
    except Exception:
        pass

    if not await db.check_round_ready(battle["id"]):
        return

    # Расчёт раунда
    b = await db.get_battle(battle["id"])
    s1 = await db.get_combat_stats(b["player1_id"])
    s2 = await db.get_combat_stats(b["player2_id"])
    name1 = (b.get("p1_name") or "Боец")[:20]
    name2 = (b.get("p2_name") or "Боец")[:20]

    c1 = {**s1, "hp": b["player1_hp"]}
    c2 = {**s2, "hp": b["player2_hp"]}
    hp1_new, hp2_new, logs = BattleMath.resolve_round(
        c1, c2,
        b["p1_attack_zone"], b["p1_block_zone"],
        b["p2_attack_zone"], b["p2_block_zone"],
        name1=name1, name2=name2,
    )

    upd = await db.resolve_round_and_advance(b["id"], hp1_new, hp2_new)
    stake = b.get("stake") or 10
    if upd["is_finished"] and upd.get("winner_id") and stake > 0:
        await db.resolve_arena_winner(b["id"], upd["winner_id"], stake)
    if upd["is_finished"]:
        await db.set_player_current_hp(b["player1_id"], hp1_new)
        await db.set_player_current_hp(b["player2_id"], hp2_new)
        loser_id = b["player2_id"] if upd["winner_id"] == b["player1_id"] else b["player1_id"]
        await db.set_trauma(loser_id, 5)

    log_str = "\n".join(logs[-4:])
    max1, max2 = s1.get("max_hp", 50), s2.get("max_hp", 50)
    bar1 = draw_hp_bar(hp1_new, max1)
    bar2 = draw_hp_bar(hp2_new, max2)

    txt_base = f"🥊 <b>Раунд {b['round_number']}</b>\n{log_str}\n\n"
    txt1 = txt_base + f"👤 Вы: {bar1}\n🆚 {name2}: {bar2}"
    txt2 = txt_base + f"👤 Вы: {bar2}\n🆚 {name1}: {bar1}"

    def _bandage_left(b: dict, is_p1: bool) -> int:
        col = "p1_bandage_uses" if is_p1 else "p2_bandage_uses"
        used = b.get(col, 0) or 0
        return max(0, BANDAGE_LIMIT - used)

    kb_p1 = kb_p2 = None
    if not upd["is_finished"]:
        kb_p1 = arena_move_keyboard(None, None, _bandage_left(upd, True))
        kb_p2 = arena_move_keyboard(None, None, _bandage_left(upd, False))

    bank = stake * 2
    winner_gain = bank - int(bank * 0.10)

    async def send_upd(tg_id, msg_id, text, is_p1):
        if not tg_id:
            return
        my_id = b["player1_id"] if is_p1 else b["player2_id"]
        kb = (kb_p1 if is_p1 else kb_p2) if not upd["is_finished"] else None
        if upd["is_finished"]:
            if upd["winner_id"] == my_id:
                text += f"\n\n🏆 <b>ПОБЕДА!</b>\n{get_victory_phrase()}\n💰 Получено: {winner_gain} кр.\n👉 /arena"
            else:
                text += f"\n\n💀 <b>ПОРАЖЕНИЕ.</b>\n{get_defeat_phrase()}\n👉 /arena"
        else:
            text += "\n\n👇 Ваш ход:"
        try:
            await callback.bot.edit_message_text(
                text, chat_id=tg_id, message_id=msg_id, reply_markup=kb, parse_mode="HTML",
            )
        except Exception:
            m = await callback.bot.send_message(tg_id, text, reply_markup=kb, parse_mode="HTML")
            await db.set_battle_message_id(b["id"], my_id, m.message_id)

    p1_tg = await get_telegram_id_by_player_id(db, b["player1_id"])
    p2_tg = await get_telegram_id_by_player_id(db, b["player2_id"])
    await send_upd(p1_tg, b.get("p1_msg_id"), txt1, True)
    await send_upd(p2_tg, b.get("p2_msg_id"), txt2, False)


@router.callback_query(F.data == "surrender_confirm")
async def arena_surrender_confirm(callback: CallbackQuery) -> None:
    player = await db.get_player_by_telegram_id(callback.from_user.id if callback.from_user else 0)
    if not player:
        return
    battle = await db.get_active_battle_for_player(player["id"])
    if not battle:
        await callback.message.edit_text("Бой уже завершён.")
        await callback.answer()
        return

    b = await db.surrender_battle(battle["id"], player["id"])
    p1_tg = await get_telegram_id_by_player_id(db, b["player1_id"])
    p2_tg = await get_telegram_id_by_player_id(db, b["player2_id"])
    _arena_selection.pop((player["id"], battle["id"]), None)

    txt = "🏳 <b>Бой завершён сдачей!</b>\n\nОдин из игроков покинул поле боя.\n👉 /arena"
    for tg_id, msg_id in [(p1_tg, b.get("p1_msg_id")), (p2_tg, b.get("p2_msg_id"))]:
        if tg_id:
            try:
                await callback.bot.edit_message_text(
                    txt, chat_id=tg_id, message_id=msg_id, reply_markup=None, parse_mode="HTML",
                )
            except Exception:
                await callback.bot.send_message(tg_id, txt, parse_mode="HTML")
    await callback.answer("Вы сдались.")


@router.callback_query(F.data == "surrender")
async def arena_surrender_ask(callback: CallbackQuery) -> None:
    player = await db.get_player_by_telegram_id(callback.from_user.id if callback.from_user else 0)
    if not player:
        return
    battle = await db.get_active_battle_for_player(player["id"])
    if not battle:
        await callback.answer("Бой уже завершён.")
        return
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    builder = InlineKeyboardBuilder()
    builder.button(text="Да, сдаться (поражение)", callback_data="surrender_confirm")
    builder.button(text="Отмена", callback_data="arena_cancel_surrender")
    builder.adjust(1)
    try:
        await callback.message.edit_text(
            "🏳 <b>Сдаться?</b>\n\nВыход = поражение. Ставка уйдёт сопернику (минус комиссия).",
            reply_markup=builder.as_markup(),
            parse_mode="HTML",
        )
    except Exception:
        pass
    await callback.answer()


@router.callback_query(F.data == "arena_cancel_surrender")
async def arena_cancel_surrender(callback: CallbackQuery) -> None:
    player = await db.get_player_by_telegram_id(callback.from_user.id if callback.from_user else 0)
    if not player:
        return
    battle = await db.get_active_battle_for_player(player["id"])
    if not battle:
        await callback.answer()
        return
    is_p1 = battle["player1_id"] == player["id"]
    my_hp = battle["player1_hp"] if is_p1 else battle["player2_hp"]
    opp_hp = battle["player2_hp"] if is_p1 else battle["player1_hp"]
    opp_name = (battle["p2_name"] if is_p1 else battle["p1_name"]) or "Соперник"
    s = await db.get_combat_stats(player["id"], for_arena=True)
    max_hp = s.get("max_hp", 50)
    txt = (
        f"⚔ <b>Бой продолжается</b>\n\n"
        f"👤 Вы: {draw_hp_bar(my_hp, max_hp)}\n"
        f"👤 {opp_name}: {draw_hp_bar(opp_hp)}\n\n"
        "👇 Ваш ход:"
    )
    await callback.message.edit_text(txt, reply_markup=_arena_kb(player["id"], battle["id"], battle=battle), parse_mode="HTML")
    await callback.answer("Отменено")
