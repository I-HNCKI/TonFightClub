"""
Battle formulas: HP, damage, dodge, crit, zone block.
"""
import random
from typing import TypedDict


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
        """Урон = (Рандом от Weapon_Min до Weapon_Max) * (1 + Сила * 0.05)."""
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
    ) -> tuple[int, int, list[str]]:
        """
        Resolve one round of PvP. Returns (new_p1_hp, new_p2_hp, log_lines).
        Zones 1=head, 2=body, 3=legs.
        """
        log: list[str] = []
        dmg1_to_2 = 0
        dmg2_to_1 = 0

        # P1 hits P2
        if BattleMath.zone_blocked(p1_attack_zone, p2_block_zone):
            log.append("Игрок 1 атаковал — Игрок 2 заблокировал.")
        else:
            base = BattleMath.base_damage(
                p1_stats["weapon_min"], p1_stats["weapon_max"], p1_stats["strength"]
            )
            dodge = random.random() * 100 < BattleMath.dodge_chance(
                p1_stats["intuition"], p2_stats["agility"]
            )
            if dodge:
                log.append("Игрок 1 атаковал — Игрок 2 увернулся.")
            else:
                crit = random.random() * 100 < BattleMath.crit_chance(
                    p1_stats["intuition"], p2_stats["agility"]
                )
                dmg1_to_2 = base * 2 if crit else base
                log.append(f"Игрок 1 нанёс {dmg1_to_2} урона Игроку 2." + (" Крит!" if crit else ""))

        # P2 hits P1
        if BattleMath.zone_blocked(p2_attack_zone, p1_block_zone):
            log.append("Игрок 2 атаковал — Игрок 1 заблокировал.")
        else:
            base = BattleMath.base_damage(
                p2_stats["weapon_min"], p2_stats["weapon_max"], p2_stats["strength"]
            )
            dodge = random.random() * 100 < BattleMath.dodge_chance(
                p2_stats["intuition"], p1_stats["agility"]
            )
            if dodge:
                log.append("Игрок 2 атаковал — Игрок 1 увернулся.")
            else:
                crit = random.random() * 100 < BattleMath.crit_chance(
                    p2_stats["intuition"], p1_stats["agility"]
                )
                dmg2_to_1 = base * 2 if crit else base
                log.append(f"Игрок 2 нанёс {dmg2_to_1} урона Игроку 1." + (" Крит!" if crit else ""))

        new_p1_hp = max(0, p1_stats["hp"] - dmg2_to_1)
        new_p2_hp = max(0, p2_stats["hp"] - dmg1_to_2)
        return new_p1_hp, new_p2_hp, log
