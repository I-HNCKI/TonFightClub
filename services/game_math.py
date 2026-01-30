"""
Battle formulas: HP, damage, dodge, crit, zone block.
Лог боя — фразы из battle_phrases (чёрный юмор БК).
"""
import random
from typing import TypedDict

from services import battle_phrases


class CombatStats(TypedDict):
    strength: int
    agility: int
    intuition: int
    stamina: int
    hp: int
    weapon_min: int
    weapon_max: int


class BattleMath:
    """Formulas for combat calculation."""

    @staticmethod
    def hp_from_stamina(stamina: int, bonus_hp: int = 0) -> int:
        """HP = Выносливость * 5 + bonus_hp."""
        return stamina * 5 + bonus_hp

    @staticmethod
    def base_damage(weapon_min: int, weapon_max: int, strength: int) -> int:
        """Урон = (Рандом от Weapon_Min до Weapon_Max) * (1 + Сила * 0.05). Минимальный урон всегда 1."""
        raw = random.randint(weapon_min, weapon_max) if weapon_max >= weapon_min else weapon_min
        return max(1, int(raw * (1 + strength * 0.05)))

    @staticmethod
    def dodge_chance(attacker_intuition: int, defender_agility: int) -> float:
        """Уворот шанс = (Ловкость врага - Интуиция атакующего) * 5. In percent 0..100."""
        return max(0, min(100, (defender_agility - attacker_intuition) * 5))

    @staticmethod
    def crit_chance(attacker_intuition: int, defender_agility: int) -> float:
        """Крит шанс = (Интуиция атакующего - Ловкость врага) * 5. In percent 0..100."""
        return max(0, min(100, (attacker_intuition - defender_agility) * 5))

    @staticmethod
    def zone_blocked(attack_zone: int, block_zone: int) -> bool:
        """Если зоны удара и блока совпадают — урон 0."""
        return attack_zone == block_zone

    @staticmethod
    def resolve_round(
        p1_stats: CombatStats,
        p2_stats: CombatStats,
        p1_attack_zone: int,
        p1_block_zone: int,
        p2_attack_zone: int,
        p2_block_zone: int,
        name1: str = "Игрок 1",
        name2: str = "Игрок 2",
    ) -> tuple[int, int, list[str]]:
        """
        Resolve one round of PvP. Returns (new_p1_hp, new_p2_hp, log_lines).
        Лог — фразы в стиле БК (попадание, блок, крит, уворот).
        """
        log: list[str] = []
        dmg1_to_2 = 0
        dmg2_to_1 = 0

        # P1 бьёт P2 (attack_zone==0 = хил, не атакует). Крит игнорирует 50% защиты.
        if p1_attack_zone == 0:
            log.append(f"{name1} выпил зелье (ход потрачен).")
        else:
            blocked1 = BattleMath.zone_blocked(p1_attack_zone, p2_block_zone)
            base1 = BattleMath.base_damage(
                p1_stats["weapon_min"], p1_stats["weapon_max"], p1_stats["strength"]
            )
            crit1 = random.random() * 100 < BattleMath.crit_chance(
                p1_stats["intuition"], p2_stats["agility"]
            )
            if blocked1 and not crit1:
                log.append(battle_phrases.build_exchange_line(name1, name2, "block"))
            else:
                dodge = random.random() * 100 < BattleMath.dodge_chance(
                    p1_stats["intuition"], p2_stats["agility"]
                )
                if dodge:
                    log.append(battle_phrases.build_exchange_line(name1, name2, "dodge"))
                else:
                    dmg1_to_2 = base1 * 2 if crit1 else base1
                    if blocked1 and crit1:
                        dmg1_to_2 = max(1, dmg1_to_2 // 2)
                    log.append(battle_phrases.build_exchange_line(
                        name1, name2, "crit" if crit1 else "hit", dmg1_to_2
                    ))

        # P2 бьёт P1
        if p2_attack_zone == 0:
            log.append(f"{name2} выпил зелье (ход потрачен).")
        else:
            blocked2 = BattleMath.zone_blocked(p2_attack_zone, p1_block_zone)
            base2 = BattleMath.base_damage(
                p2_stats["weapon_min"], p2_stats["weapon_max"], p2_stats["strength"]
            )
            crit2 = random.random() * 100 < BattleMath.crit_chance(
                p2_stats["intuition"], p1_stats["agility"]
            )
            if blocked2 and not crit2:
                log.append(battle_phrases.build_exchange_line(name2, name1, "block"))
            else:
                dodge = random.random() * 100 < BattleMath.dodge_chance(
                    p2_stats["intuition"], p1_stats["agility"]
                )
                if dodge:
                    log.append(battle_phrases.build_exchange_line(name2, name1, "dodge"))
                else:
                    dmg2_to_1 = base2 * 2 if crit2 else base2
                    if blocked2 and crit2:
                        dmg2_to_1 = max(1, dmg2_to_1 // 2)
                    log.append(battle_phrases.build_exchange_line(
                        name2, name1, "crit" if crit2 else "hit", dmg2_to_1
                    ))

        new_p1_hp = max(0, p1_stats["hp"] - dmg2_to_1)
        new_p2_hp = max(0, p2_stats["hp"] - dmg1_to_2)
        return new_p1_hp, new_p2_hp, log
