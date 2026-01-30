"""
PvP Arena: find opponent, turn-based combat (attack/block zones), round log to both.
Updates: Edits messages instead of spamming, uses real usernames.
"""
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
from aiogram.exceptions import TelegramBadRequest

from keyboards import arena_keyboard, arena_move_keyboard
from services.game_math import BattleMath, CombatStats
from database.db import Database
from database.db import db

router = Router(name="arena")


async def get_telegram_id_by_player_id(db: Database, player_id: int) -> int | None:
    async with db.pool.acquire() as conn:
        row = await conn.fetchrow("SELECT telegram_id FROM players WHERE id = $1", player_id)
        return row["telegram_id"] if row else None


@router.message(F.text == "🏟 Арена (PvP)")
@router.message(Command("arena"))
async def arena_menu(message: Message) -> None:
    player = await db.get_player_by_telegram_id(message.from_user.id if message.from_user else 0)
    if not player:
        await message.answer("Сначала /start")
        return

    # Получаем активный бой с именами
    battle = await db.get_active_battle_for_player(player["id"])
    
    if battle:
        # Определяем, кто есть кто
        is_p1 = battle['player1_id'] == player['id']
        my_hp = battle['player1_hp'] if is_p1 else battle['player2_hp']
        opp_hp = battle['player2_hp'] if is_p1 else battle['player1_hp']
        opp_name = battle['p2_name'] if is_p1 else battle['p1_name']

        await message.answer(
            f"У вас уже есть активный бой #{battle['id']} против <b>{opp_name}</b>.\n"
            f"Ваш HP: {my_hp} | HP {opp_name}: {opp_hp}\n"
            "Сделайте ход!",
            reply_markup=arena_move_keyboard(),
            parse_mode="HTML"
        )
        return

    await message.answer(
        "🏟 <b>Арена PvP</b>\n\nНажмите «Найти соперника». Когда найдётся противник — начнётся бой.",
        reply_markup=arena_keyboard(),
        parse_mode="HTML",
    )


@router.callback_query(F.data == "arena_find")
async def arena_find(callback: CallbackQuery) -> None:
    player = await db.get_player_by_telegram_id(callback.from_user.id if callback.from_user else 0)
    if not player:
        await callback.answer("Сначала /start")
        return

    # Пытаемся найти соперника
    status, battle_id = await db.arena_join_queue(player["id"])

    if status == "waiting":
        await callback.message.edit_text(
            "⏳ <b>Поиск соперника...</b>\nВы в очереди. Ожидайте...",
            reply_markup=arena_keyboard(),
            parse_mode="HTML"
        )
        await callback.answer()
        return

    if status == "matched" and battle_id:
        # Бой создан! Получаем данные боя с именами
        battle = await db.get_battle(battle_id)
        if not battle:
            await callback.answer("Ошибка создания боя")
            return

        p1_tg = await get_telegram_id_by_player_id(db, battle["player1_id"])
        p2_tg = await get_telegram_id_by_player_id(db, battle["player2_id"])
        
        # Текст для Игрока 1
        text_p1 = (
            f"⚔ <b>Бой начался!</b>\n\n"
            f"Вы: <b>{battle['p1_name']}</b> ({battle['player1_hp']} HP)\n"
            f"Против: <b>{battle['p2_name']}</b> ({battle['player2_hp']} HP)\n\n"
            f"Раунд 1. Выберите зону атаки и защиты:"
        )
        # Текст для Игрока 2
        text_p2 = (
            f"⚔ <b>Бой начался!</b>\n\n"
            f"Вы: <b>{battle['p2_name']}</b> ({battle['player2_hp']} HP)\n"
            f"Против: <b>{battle['p1_name']}</b> ({battle['player1_hp']} HP)\n\n"
            f"Раунд 1. Выберите зону атаки и защиты:"
        )

        kb = arena_move_keyboard()

        # Отправляем сообщение P1 и СОХРАНЯЕМ ID
        if p1_tg:
            msg1 = await callback.bot.send_message(p1_tg, text_p1, reply_markup=kb, parse_mode="HTML")
            await db.set_battle_message_id(battle_id, battle["player1_id"], msg1.message_id)

        # Отправляем сообщение P2 и СОХРАНЯЕМ ID
        if p2_tg:
            msg2 = await callback.bot.send_message(p2_tg, text_p2, reply_markup=kb, parse_mode="HTML")
            await db.set_battle_message_id(battle_id, battle["player2_id"], msg2.message_id)

        # Удаляем сообщение "поиск" у того, кто нажал кнопку последним (чтобы не висело лишнее)
        try:
            await callback.message.delete()
        except:
            pass
            
        return

    await callback.answer("Ошибка")


@router.callback_query(F.data == "arena_leave")
async def arena_leave(callback: CallbackQuery) -> None:
    player = await db.get_player_by_telegram_id(callback.from_user.id if callback.from_user else 0)
    if not player:
        await callback.answer("Сначала /start")
        return
    await db.arena_leave_queue(player["id"])
    await callback.message.edit_text("Вы вышли из очереди.", reply_markup=arena_keyboard())
    await callback.answer("Выход из очереди")


@router.callback_query(F.data.startswith("move_"))
async def arena_move(callback: CallbackQuery) -> None:
    # Разбор данных callback
    parts = callback.data.split("_")
    if len(parts) != 3:
        await callback.answer("Неверный ход")
        return
    try:
        atk_zone = int(parts[1])
        blk_zone = int(parts[2])
    except ValueError:
        await callback.answer("Ошибка")
        return
    
    player = await db.get_player_by_telegram_id(callback.from_user.id if callback.from_user else 0)
    if not player:
        await callback.answer("Сначала /start")
        return

    battle = await db.get_active_battle_for_player(player["id"])
    if not battle:
        await callback.message.edit_text("Бой не найден или завершен.", reply_markup=None)
        return

    # Делаем ход
    ok, msg = await db.make_move(battle["id"], player["id"], atk_zone, blk_zone)
    if not ok:
        await callback.answer(msg, show_alert=True)
        return

    # Если ход принят, обновляем текст на "Ожидание"
    await callback.answer("Ход принят")
    
    # Получаем имена для красивого текста ожидания
    is_p1 = battle['player1_id'] == player['id']
    opp_name = battle['p2_name'] if is_p1 else battle['p1_name']
    
    wait_text = (
        f"✅ <b>Ход принят!</b>\n"
        f"Вы атаковали зону {atk_zone}, блок {blk_zone}.\n"
        f"Ожидаем ход соперника ({opp_name})..."
    )
    
    try:
        await callback.message.edit_text(wait_text, reply_markup=None, parse_mode="HTML")
    except TelegramBadRequest:
        pass # Если текст не изменился (редкий случай)

    # Проверяем, готов ли раунд
    ready = await db.check_round_ready(battle["id"])
    if not ready:
        return # Ждем второго

    # === РАСЧЕТ РАУНДА ===
    b = await db.get_battle(battle["id"])
    if not b or b["is_finished"]:
        return

    p1_stats = await db.get_combat_stats(b["player1_id"])
    p2_stats = await db.get_combat_stats(b["player2_id"])

    # Собираем данные для математики
    p1_combat: CombatStats = {
        "strength": p1_stats["strength"],
        "agility": p1_stats["agility"],
        "intuition": p1_stats["intuition"],
        "stamina": p1_stats["stamina"],
        "hp": b["player1_hp"],
        "weapon_min": p1_stats.get("weapon_min", 1),
        "weapon_max": p1_stats.get("weapon_max", 2),
    }
    p2_combat: CombatStats = {
        "strength": p2_stats["strength"],
        "agility": p2_stats["agility"],
        "intuition": p2_stats["intuition"],
        "stamina": p2_stats["stamina"],
        "hp": b["player2_hp"],
        "weapon_min": p2_stats.get("weapon_min", 1),
        "weapon_max": p2_stats.get("weapon_max", 2),
    }

    # Считаем урон
    new_p1_hp, new_p2_hp, log_lines = BattleMath.resolve_round(
        p1_combat, p2_combat,
        b["p1_attack_zone"], b["p1_block_zone"],
        b["p2_attack_zone"], b["p2_block_zone"],
    )

    # Обновляем базу
    updated = await db.resolve_round_and_advance(b["id"], new_p1_hp, new_p2_hp)

    # Телеграм ID для отправки
    p1_tg = await get_telegram_id_by_player_id(db, b["player1_id"])
    p2_tg = await get_telegram_id_by_player_id(db, b["player2_id"])

    # Формируем лог
    round_log = "\n".join(log_lines)

    # === РАССЫЛКА ИТОГОВ РАУНДА (РЕДАКТИРОВАНИЕ) ===
    # Нам нужно сформировать разный текст для P1 и P2 (чтобы было "Вы" и "Противник")
    
    # --- Текст для Игрока 1 ---
    text_p1 = (
        f"🥊 <b>Раунд {b['round_number']} завершён!</b>\n\n"
        f"{round_log}\n\n"
        f"👤 <b>Вы ({b['p1_name']})</b>: {new_p1_hp} HP\n"
        f"👤 <b>{b['p2_name']}</b>: {new_p2_hp} HP"
    )
    
    # --- Текст для Игрока 2 ---
    text_p2 = (
        f"🥊 <b>Раунд {b['round_number']} завершён!</b>\n\n"
        f"{round_log}\n\n"
        f"👤 <b>Вы ({b['p2_name']})</b>: {new_p2_hp} HP\n"
        f"👤 <b>{b['p1_name']}</b>: {new_p1_hp} HP"
    )

    is_finished = updated["is_finished"]
    winner_id = updated["winner_id"]
    kb = None if is_finished else arena_move_keyboard()

    # --- Обновляем Игрока 1 ---
    if p1_tg and b.get("p1_msg_id"):
        final_text = text_p1
        if is_finished:
            if winner_id == b["player1_id"]:
                final_text += "\n\n🏆 <b>ПОБЕДА!</b> Вы выиграли бой!"
            else:
                final_text += "\n\n💀 <b>ПОРАЖЕНИЕ.</b> Вы проиграли."
            final_text += "\n\nВернуться: /arena"
        else:
            final_text += "\n\n👇 <b>Выберите ход на следующий раунд:</b>"

        try:
            await callback.bot.edit_message_text(
                text=final_text,
                chat_id=p1_tg,
                message_id=b["p1_msg_id"],
                reply_markup=kb,
                parse_mode="HTML"
            )
        except TelegramBadRequest:
            # Если сообщение слишком старое или удалено, шлем новое
            new_msg = await callback.bot.send_message(p1_tg, final_text, reply_markup=kb, parse_mode="HTML")
            await db.set_battle_message_id(b["id"], b["player1_id"], new_msg.message_id)

    # --- Обновляем Игрока 2 ---
    if p2_tg and b.get("p2_msg_id"):
        final_text = text_p2
        if is_finished:
            if winner_id == b["player2_id"]:
                final_text += "\n\n🏆 <b>ПОБЕДА!</b> Вы выиграли бой!"
            else:
                final_text += "\n\n💀 <b>ПОРАЖЕНИЕ.</b> Вы проиграли."
            final_text += "\n\nВернуться: /arena"
        else:
            final_text += "\n\n👇 <b>Выберите ход на следующий раунд:</b>"

        try:
            await callback.bot.edit_message_text(
                text=final_text,
                chat_id=p2_tg,
                message_id=b["p2_msg_id"],
                reply_markup=kb,
                parse_mode="HTML"
            )
        except TelegramBadRequest:
             # Если сообщение слишком старое или удалено, шлем новое
            new_msg = await callback.bot.send_message(p2_tg, final_text, reply_markup=kb, parse_mode="HTML")
            await db.set_battle_message_id(b["id"], b["player2_id"], new_msg.message_id)