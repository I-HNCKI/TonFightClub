"""
Глобальный рейтинг: ТОП-10 и ТОП-100 с пагинацией. TON FIGHT CLUB.
"""
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command
from aiogram.utils.keyboard import InlineKeyboardBuilder

from database.db import db

router = Router(name="top")

SERVER_NAME = "TON FIGHT CLUB"
TOP10_LIMIT = 10
TOP100_LIMIT = 100
TOP100_PAGE_SIZE = 25


def _display_name(name: str) -> str:
    """@username если похоже на юзернейм, иначе как есть."""
    if not name or name == "Игрок":
        return name or "Игрок"
    s = name.strip()
    if s and not s.startswith("@"):
        return f"@{s}"
    return s


def _top10_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="📜 Показать ТОП-100", callback_data="show_top100"),
    )
    return builder.as_markup()


def _top100_pagination_keyboard(page: int, total_pages: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    if total_pages <= 1:
        builder.row(
            InlineKeyboardButton(text="◀️ ТОП-10", callback_data="show_top"),
        )
        return builder.as_markup()
    row = []
    if page > 1:
        row.append(InlineKeyboardButton(text="⬅️ Назад", callback_data=f"top100_page_{page - 1}"))
    row.append(
        InlineKeyboardButton(
            text=f"📜 ТОП-100 ({page}/{total_pages})",
            callback_data="noop",
        )
    )
    if page < total_pages:
        row.append(InlineKeyboardButton(text="Вперед ➡️", callback_data=f"top100_page_{page + 1}"))
    builder.row(*row)
    builder.row(InlineKeyboardButton(text="◀️ ТОП-10", callback_data="show_top"))
    return builder.as_markup()


async def _get_player_rank_text(telegram_id: int) -> str:
    player = await db.get_player_by_telegram_id(telegram_id)
    if not player:
        return "Ваше место в рейтинге: —"
    rank = await db.get_user_rank(player["id"])
    if rank is None:
        return "Ваше место в рейтинге: —"
    return f"Ваше место в рейтинге: #{rank}"


def _build_top10_text(leaders: list[dict], rank_line: str) -> str:
    lines = [f"🏆 <b>ЗАЛ СЛАВЫ {SERVER_NAME} (TOP-10)</b>\n"]
    medals = {1: "🥇", 2: "🥈", 3: "🥉"}
    for i, p in enumerate(leaders, 1):
        icon = medals.get(i, "🎖")
        name = _display_name(p.get("name") or "Игрок")
        lvl = p.get("level", 0)
        cls = p.get("class_name") or "Без класса"
        lines.append(f"{i}. {icon} {name} | Lvl {lvl} ({cls})")
    lines.append("----------------------")
    lines.append(rank_line)
    return "\n".join(lines)


def _build_top100_page_text(leaders: list[dict], page: int, total_pages: int, rank_line: str) -> str:
    start = (page - 1) * TOP100_PAGE_SIZE
    chunk = leaders[start : start + TOP100_PAGE_SIZE]
    lines = [f"🏆 <b>ЗАЛ СЛАВЫ {SERVER_NAME} — ТОП-100</b> (стр. {page}/{total_pages})\n"]
    medals = {1: "🥇", 2: "🥈", 3: "🥉"}
    for idx, p in enumerate(chunk, start=start + 1):
        icon = medals.get(idx, "🎖")
        name = _display_name(p.get("name") or "Игрок")
        lvl = p.get("level", 0)
        cls = p.get("class_name") or "Без класса"
        lines.append(f"{idx}. {icon} {name} | Lvl {lvl} ({cls})")
    lines.append("----------------------")
    lines.append(rank_line)
    return "\n".join(lines)


@router.message(F.text == "🏆 Топ игроков")
@router.message(Command("top"))
async def cmd_top(message: Message) -> None:
    leaders = await db.get_leaderboard(TOP10_LIMIT)
    rank_line = await _get_player_rank_text(message.from_user.id if message.from_user else 0)
    if not leaders:
        await message.answer(
            "В этом мире пока нет героев... Зарегистрируйтесь и станьте первым!",
            reply_markup=_top10_keyboard(),
        )
        return
    text = _build_top10_text(leaders, rank_line)
    await message.answer(text, reply_markup=_top10_keyboard())


@router.callback_query(F.data == "show_top")
async def cb_show_top(callback: CallbackQuery) -> None:
    await callback.answer()
    telegram_id = callback.from_user.id if callback.from_user else 0
    leaders = await db.get_leaderboard(TOP10_LIMIT)
    rank_line = await _get_player_rank_text(telegram_id)
    if not leaders:
        await callback.message.edit_text(
            "В этом мире пока нет героев... Зарегистрируйтесь и станьте первым!",
            reply_markup=_top10_keyboard(),
        )
        return
    text = _build_top10_text(leaders, rank_line)
    try:
        await callback.message.edit_text(text, reply_markup=_top10_keyboard())
    except Exception:
        await callback.message.answer(text, reply_markup=_top10_keyboard())


@router.callback_query(F.data == "show_top100")
async def cb_show_top100(callback: CallbackQuery) -> None:
    await callback.answer()
    telegram_id = callback.from_user.id if callback.from_user else 0
    leaders = await db.get_leaderboard(TOP100_LIMIT)
    rank_line = await _get_player_rank_text(telegram_id)
    total_pages = max(1, (len(leaders) + TOP100_PAGE_SIZE - 1) // TOP100_PAGE_SIZE)
    page = 1
    text = _build_top100_page_text(leaders, page, total_pages, rank_line)
    kb = _top100_pagination_keyboard(page, total_pages)
    try:
        await callback.message.edit_text(text, reply_markup=kb)
    except Exception:
        await callback.message.answer(text, reply_markup=kb)


@router.callback_query(F.data.startswith("top100_page_"))
async def cb_top100_page(callback: CallbackQuery) -> None:
    await callback.answer()
    try:
        page = int(callback.data.replace("top100_page_", ""))
    except ValueError:
        page = 1
    telegram_id = callback.from_user.id if callback.from_user else 0
    leaders = await db.get_leaderboard(TOP100_LIMIT)
    rank_line = await _get_player_rank_text(telegram_id)
    total_pages = max(1, (len(leaders) + TOP100_PAGE_SIZE - 1) // TOP100_PAGE_SIZE)
    page = max(1, min(page, total_pages))
    text = _build_top100_page_text(leaders, page, total_pages, rank_line)
    kb = _top100_pagination_keyboard(page, total_pages)
    try:
        await callback.message.edit_text(text, reply_markup=kb)
    except Exception:
        await callback.message.answer(text, reply_markup=kb)


@router.callback_query(F.data == "noop")
async def cb_noop(callback: CallbackQuery) -> None:
    await callback.answer()
