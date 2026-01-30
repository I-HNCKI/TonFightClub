"""
Hard Reset: новая математика боя.
HP = 30 + level*5 + stamina*5; XP curve (level**2)*100;
Armor Reduction = armor/(armor+50); Base_Dmg = Weapon_Dmg + Str*0.5;
Crit 1.5x + игнор 50% брони; Dodge +0.5% за AGI; Crit Chance +0.5% за INT.
"""
import random
import math
from typing import TypedDict

from services import battle_phrases


class CombatStats(TypedDict):
    strength: int
    agility: int
    intuition: int
    stamina: int
    hp: int
    max_hp: int
    weapon_min: int
    weapon_max: int
    armor: int
    level: int


class BattleMath:
    """Формулы по спецификации Hard Reset."""

    @staticmethod
    def max_hp(level: int, stamina: int) -> int:
        """MaxHP = 30 + (level * 5) + (stamina * 5)."""
        return 30 + (level * 5) + (stamina * 5)

    @staticmethod
    def xp_for_next_level(current_level: int) -> int:
        """Опыт для след. уровня = (Current_Level ** 2) * 100."""
        return (current_level ** 2) * 100

    @staticmethod
    def potion_heal(max_hp: int) -> int:
        """Зелье восстанавливает 25% от MaxHP (округление вверх)."""
        return max(1, math.ceil(max_hp * 0.25))

    @staticmethod
    def armor_reduction_percent(armor: int) -> float:
        """Reduction_Percent = armor / (armor + 50). 10 брони ≈ 16%, 50 брони = 50%."""
        if armor <= 0:
            return 0.0
        return armor / (armor + 50)

    @staticmethod
    def base_damage(weapon_min: int, weapon_max: int, strength: int) -> float:
        """Base_Dmg = Weapon_Dmg + (Strength * 0.5). Weapon_Dmg = random(min, max)."""
        w_dmg = random.randint(weapon_min, weapon_max) if weapon_max >= weapon_min else weapon_min
        return w_dmg + (strength * 0.5)

    @staticmethod
    def final_damage(base_dmg: float, defender_armor: int, is_crit: bool = False) -> int:
        """
        Final_Dmg = Base_Dmg * (1 - Reduction_Percent).
        Крит: игнор 50% брони цели (effective_armor = armor * 0.5).
        Урон не меньше 1 при попадании.
        """
        if defender_armor <= 0:
            dmg = base_dmg * 1.5 if is_crit else base_dmg
            return max(1, int(round(dmg)))
        effective_armor = defender_armor * 0.5 if is_crit else defender_armor
        reduction = effective_armor / (effective_armor + 50)
        dmg = base_dmg * (1 - reduction)
        if is_crit:
            dmg *= 1.5
        return max(1, int(round(dmg)))

    @staticmethod
    def dodge_chance(defender_agility: int) -> float:
        """+0.5% Dodge Chance за очко Ловкости. In percent 0..100."""
        return max(0, min(100, defender_agility * 0.5))

    @staticmethod
    def crit_chance(attacker_intuition: int) -> float:
        """+0.5% Crit Chance за очко Интуиции. In percent 0..100."""
        return max(0, min(100, attacker_intuition * 0.5))

    @staticmethod
    def zone_blocked(attack_zone: int, block_zone: int) -> bool:
        """Зоны совпали — блок."""
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
        Один раунд PvP. attack_zone==0 = хил (не атакует). Возвращает (new_p1_hp, new_p2_hp, log).
        """
        log: list[str] = []
        dmg1_to_2 = 0
        dmg2_to_1 = 0

        # P1 бьёт P2 (0 = не бьёт, только хил в другом месте)
        if p1_attack_zone == 0:
            log.append(f"{name1} выпил зелье (Free Action).")
        else:
            blocked1 = BattleMath.zone_blocked(p1_attack_zone, p2_block_zone)
            base1 = BattleMath.base_damage(
                p1_stats["weapon_min"], p1_stats["weapon_max"], p1_stats["strength"]
            )
            crit1 = random.random() * 100 < BattleMath.crit_chance(p1_stats["intuition"])
            if blocked1 and not crit1:
                log.append(battle_phrases.build_exchange_line(name1, name2, "block"))
            else:
                dodge = random.random() * 100 < BattleMath.dodge_chance(p2_stats["agility"])
                if dodge:
                    log.append(battle_phrases.build_exchange_line(name1, name2, "dodge"))
                else:
                    dmg1_to_2 = BattleMath.final_damage(
                        base1, p2_stats.get("armor", 0), is_crit=crit1
                    )
                    log.append(battle_phrases.build_exchange_line(
                        name1, name2, "crit" if crit1 else "hit", dmg1_to_2
                    ))

        # P2 бьёт P1
        if p2_attack_zone == 0:
            log.append(f"{name2} выпил зелье (Free Action).")
        else:
            blocked2 = BattleMath.zone_blocked(p2_attack_zone, p1_block_zone)
            base2 = BattleMath.base_damage(
                p2_stats["weapon_min"], p2_stats["weapon_max"], p2_stats["strength"]
            )
            crit2 = random.random() * 100 < BattleMath.crit_chance(p2_stats["intuition"])
            if blocked2 and not crit2:
                log.append(battle_phrases.build_exchange_line(name2, name1, "block"))
            else:
                dodge = random.random() * 100 < BattleMath.dodge_chance(p1_stats["agility"])
                if dodge:
                    log.append(battle_phrases.build_exchange_line(name2, name1, "dodge"))
                else:
                    dmg2_to_1 = BattleMath.final_damage(
                        base2, p1_stats.get("armor", 0), is_crit=crit2
                    )
                    log.append(battle_phrases.build_exchange_line(
                        name2, name1, "crit" if crit2 else "hit", dmg2_to_1
                    ))

        new_p1_hp = max(0, p1_stats["hp"] - dmg2_to_1)
        new_p2_hp = max(0, p2_stats["hp"] - dmg1_to_2)
        return new_p1_hp, new_p2_hp, log
