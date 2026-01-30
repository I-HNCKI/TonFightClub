"""
Фразы лога боя в стиле БК (чёрный юмор).
Используются для: попадание, блок, крит, уворот.
"""
import random
from typing import Optional

# Попадание (атакующий попал)
PHRASE_HIT = [
    "прописал в челюсть",
    "врезал по рёбрам — хруст душевный",
    "достал до печёнки",
    "заехал в корпус — противник крякнул",
    "прошёлся по рёбрам",
    "вмазал в челюсть — звёзды в глазах",
    "достал в солнечное сплетение",
    "врезал так, что искры из глаз",
]

# Блок (защита сработала)
PHRASE_BLOCK = [
    "блокировал удар, но искры из глаз посыпались",
    "принял на блок — зубы задребезжали",
    "закрылся, но звон в ушах остался",
    "отбил удар, однако нервы пошатнулись",
    "заблокировал — зато потом полчаса пальцы не разгибались",
    "принял удар на предплечье — зато живой",
    "отбил, но искры из глаз — как фейерверк",
]

# Крит (критический удар)
PHRASE_CRIT = [
    "разнёс в хлам — КРИТ!",
    "вложился по полной — крит, противник не рад",
    "поймал момент — крит! звёзды и птички",
    "добил как следует — крит, искры полетели",
    "врезал от души — КРИТ! противник вспомнил бабушку",
]

# Уворот (защищающийся увернулся)
PHRASE_DODGE = [
    "изящно увернулся, как кошка от тапка",
    "ушел в сторону — удар прошёл в пустоту",
    "отпрыгнул в последний момент",
    "уклонился — ветер от удара волосы всколыхнул",
    "увернулся так, что атакующий сам чуть не упал",
    "слился с тенью — удар мимо",
]

# Финальные фразы: победа
PHRASE_VICTORY = [
    "Противник рухнул. Триумф!",
    "Враг повержен. Слава победителю!",
    "Оппонент сдал позиции. Победа за тобой!",
    "Бой окончен — ты на ногах, он нет.",
]

# Финальные фразы: поражение
PHRASE_DEFEAT = [
    "Земля приблизилась неожиданно быстро. Поражение.",
    "Звёзды погасли. Ты проиграл.",
    "Противник выстоял. На этот раз не твой день.",
    "Нокаут. В следующий раз повезёт.",
]


def get_hit_phrase() -> str:
    return random.choice(PHRASE_HIT)


def get_block_phrase() -> str:
    return random.choice(PHRASE_BLOCK)


def get_crit_phrase() -> str:
    return random.choice(PHRASE_CRIT)


def get_dodge_phrase() -> str:
    return random.choice(PHRASE_DODGE)


def get_victory_phrase() -> str:
    return random.choice(PHRASE_VICTORY)


def get_defeat_phrase() -> str:
    return random.choice(PHRASE_DEFEAT)


def build_exchange_line(
    attacker_name: str,
    defender_name: str,
    outcome: str,  # "block" | "dodge" | "hit" | "crit"
    damage: int = 0,
) -> str:
    """Собирает одну строку лога для обмена ударами."""
    if outcome == "block":
        return f"{defender_name} {get_block_phrase()}."
    if outcome == "dodge":
        return f"{defender_name} {get_dodge_phrase()} — удар {attacker_name} прошёл мимо."
    if outcome == "crit":
        return f"{attacker_name} {get_crit_phrase()} ({damage} урона)."
    # hit
    return f"{attacker_name} {get_hit_phrase()} — {defender_name} получил {damage} урона."
