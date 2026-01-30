"""
Database layer: PostgreSQL via asyncpg.
Creates tables on init, provides all SQL operations.
Updated: Added surrender logic and auto-cleanup for stale battles.
"""
import os
import logging
from typing import Optional

import asyncpg
from asyncpg import Pool

logger = logging.getLogger(__name__)


class Database:
    def __init__(self):
        self._pool: Optional[Pool] = None

    async def connect(self) -> None:
        self._pool = await asyncpg.create_pool(
            host=os.getenv("DB_HOST", "localhost"),
            port=int(os.getenv("DB_PORT", "5432")),
            database=os.getenv("DB_NAME", "combats_db"),
            user=os.getenv("DB_USER"),
            password=os.getenv("DB_PASS"),
            min_size=1,
            max_size=10,
            command_timeout=60,
        )
        await self.init()

    async def close(self) -> None:
        if self._pool:
            await self._pool.close()
            self._pool = None

    @property
    def pool(self) -> Pool:
        if self._pool is None:
            raise RuntimeError("Database not connected")
        return self._pool

    async def init(self) -> None:
        """Create tables if they do not exist."""
        async with self.pool.acquire() as conn:
            # players
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS players (
                    id SERIAL PRIMARY KEY,
                    telegram_id BIGINT UNIQUE NOT NULL,
                    username TEXT
                )
            """)
            # player_stats (stamina default 1 для ребаланса)
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS player_stats (
                    player_id INTEGER PRIMARY KEY REFERENCES players(id) ON DELETE CASCADE,
                    strength INTEGER NOT NULL DEFAULT 1,
                    agility INTEGER NOT NULL DEFAULT 1,
                    intuition INTEGER NOT NULL DEFAULT 1,
                    stamina INTEGER NOT NULL DEFAULT 1,
                    free_points INTEGER NOT NULL DEFAULT 0,
                    credits INTEGER NOT NULL DEFAULT 0,
                    experience INTEGER NOT NULL DEFAULT 0,
                    level INTEGER NOT NULL DEFAULT 1,
                    current_hp INTEGER,
                    hp_updated_at TIMESTAMP WITH TIME ZONE
                )
            """)
            try:
                await conn.execute("ALTER TABLE player_stats ADD COLUMN IF NOT EXISTS current_hp INTEGER")
                await conn.execute("ALTER TABLE player_stats ADD COLUMN IF NOT EXISTS hp_updated_at TIMESTAMP WITH TIME ZONE")
                await conn.execute("ALTER TABLE player_stats ADD COLUMN IF NOT EXISTS trauma_end_at TIMESTAMP WITH TIME ZONE")
            except Exception:
                pass
            # items (slot: weapon, chest, legs, potion; armor для поглощения урона)
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS items (
                    id SERIAL PRIMARY KEY,
                    name TEXT NOT NULL,
                    slot TEXT NOT NULL,
                    min_damage INTEGER NOT NULL DEFAULT 0,
                    max_damage INTEGER NOT NULL DEFAULT 0,
                    bonus_str INTEGER NOT NULL DEFAULT 0,
                    bonus_hp INTEGER NOT NULL DEFAULT 0,
                    armor INTEGER NOT NULL DEFAULT 0,
                    price INTEGER NOT NULL DEFAULT 0
                )
            """)
            # inventory
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS inventory (
                    id SERIAL PRIMARY KEY,
                    player_id INTEGER NOT NULL REFERENCES players(id) ON DELETE CASCADE,
                    item_id INTEGER NOT NULL REFERENCES items(id) ON DELETE CASCADE,
                    is_equipped BOOLEAN NOT NULL DEFAULT FALSE
                )
            """)
            # Зелья игрока (купленные потионы)
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS player_potions (
                    player_id INTEGER NOT NULL REFERENCES players(id) ON DELETE CASCADE,
                    item_id INTEGER NOT NULL REFERENCES items(id) ON DELETE CASCADE,
                    quantity INTEGER NOT NULL DEFAULT 0,
                    PRIMARY KEY (player_id, item_id)
                )
            """)
            # PvP battles (potion_used — зелье 1 раз за бой, Free Action)
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS battles (
                    id SERIAL PRIMARY KEY,
                    player1_id INTEGER NOT NULL REFERENCES players(id) ON DELETE CASCADE,
                    player2_id INTEGER NOT NULL REFERENCES players(id) ON DELETE CASCADE,
                    player1_hp INTEGER NOT NULL,
                    player2_hp INTEGER NOT NULL,
                    round_number INTEGER NOT NULL DEFAULT 1,
                    p1_attack_zone INTEGER,
                    p1_block_zone INTEGER,
                    p2_attack_zone INTEGER,
                    p2_block_zone INTEGER,
                    is_finished BOOLEAN NOT NULL DEFAULT FALSE,
                    winner_id INTEGER REFERENCES players(id),
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                    p1_msg_id INTEGER,
                    p2_msg_id INTEGER,
                    stake INTEGER NOT NULL DEFAULT 0,
                    p1_potion_used BOOLEAN NOT NULL DEFAULT FALSE,
                    p2_potion_used BOOLEAN NOT NULL DEFAULT FALSE
                )
            """)
            
            # Миграция колонок (если таблица уже была)
            try:
                await conn.execute("ALTER TABLE battles ADD COLUMN IF NOT EXISTS p1_msg_id INTEGER")
                await conn.execute("ALTER TABLE battles ADD COLUMN IF NOT EXISTS p2_msg_id INTEGER")
                await conn.execute("ALTER TABLE battles ADD COLUMN IF NOT EXISTS p1_potion_used BOOLEAN NOT NULL DEFAULT FALSE")
                await conn.execute("ALTER TABLE battles ADD COLUMN IF NOT EXISTS p2_potion_used BOOLEAN NOT NULL DEFAULT FALSE")
            except Exception:
                pass

            # Arena queue
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS arena_queue (
                    player_id INTEGER PRIMARY KEY REFERENCES players(id) ON DELETE CASCADE,
                    joined_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
                )
            """)
            # Shadow fights (PvE vs AI; potion_used — зелье 1 раз за бой)
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS shadow_fights (
                    id SERIAL PRIMARY KEY,
                    player_id INTEGER NOT NULL REFERENCES players(id) ON DELETE CASCADE,
                    shadow_hp INTEGER NOT NULL,
                    player_hp INTEGER NOT NULL,
                    round INTEGER NOT NULL DEFAULT 1,
                    is_finished BOOLEAN NOT NULL DEFAULT FALSE,
                    potion_used BOOLEAN NOT NULL DEFAULT FALSE
                )
            """)
            try:
                await conn.execute("ALTER TABLE shadow_fights ADD COLUMN IF NOT EXISTS potion_used BOOLEAN NOT NULL DEFAULT FALSE")
            except Exception:
                pass
            # System balance (commission)
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS system_balance (
                    id SERIAL PRIMARY KEY,
                    total_commission INTEGER NOT NULL DEFAULT 0
                )
            """)
            try:
                await conn.execute("ALTER TABLE battles ADD COLUMN IF NOT EXISTS stake INTEGER NOT NULL DEFAULT 0")
                await conn.execute("ALTER TABLE items ADD COLUMN IF NOT EXISTS armor INTEGER NOT NULL DEFAULT 0")
            except Exception:
                pass
        await self._init_system_balance()
        await self.add_initial_items()
        logger.info("Database init complete")

    async def _init_system_balance(self) -> None:
        """Одна строка с total_commission = 0, если таблица пуста."""
        async with self.pool.acquire() as conn:
            n = await conn.fetchval("SELECT COUNT(*) FROM system_balance")
            if not n or n == 0:
                await conn.execute("INSERT INTO system_balance (total_commission) VALUES (0)")

    async def add_initial_items(self) -> None:
        async with self.pool.acquire() as conn:
            n = await conn.fetchval("SELECT COUNT(*) FROM items")
            if n and n > 0:
                has_potion = await conn.fetchval("SELECT 1 FROM items WHERE slot = 'potion' LIMIT 1")
                if not has_potion:
                    await conn.execute("""
                        INSERT INTO items (name, slot, min_damage, max_damage, bonus_str, bonus_hp, armor, price)
                        VALUES ('Малое зелье жизни', 'potion', 0, 0, 0, 0, 0, 50)
                    """)
                return
            await conn.execute("""
                INSERT INTO items (name, slot, min_damage, max_damage, bonus_str, bonus_hp, armor, price)
                VALUES
                    ('Нож', 'weapon', 1, 3, 0, 0, 0, 10),
                    ('Меч', 'weapon', 3, 6, 0, 0, 0, 25),
                    ('Броня', 'chest', 0, 0, 0, 0, 10, 30),
                    ('Ржавый нож', 'weapon', 1, 2, 0, 0, 0, 3),
                    ('Малое зелье жизни', 'potion', 0, 0, 0, 0, 0, 50)
            """)
        logger.info("Initial items added")

    # ----- Player -----
    async def get_player_by_telegram_id(self, telegram_id: int) -> Optional[dict]:
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT id, telegram_id, username FROM players WHERE telegram_id = $1",
                telegram_id,
            )
            return dict(row) if row else None

    async def create_player(self, telegram_id: int, username: Optional[str]) -> dict:
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                INSERT INTO players (telegram_id, username)
                VALUES ($1, $2)
                RETURNING id, telegram_id, username
                """,
                telegram_id,
                username,
            )
            pid = row["id"]
            await conn.execute(
                "INSERT INTO player_stats (player_id, strength, agility, intuition, stamina) VALUES ($1, 1, 1, 1, 1)",
                pid,
            )
            return dict(row)
    
    async def update_player_name(self, telegram_id: int, new_name: str) -> None:
        """Обновляет имя игрока (фикс None)."""
        async with self.pool.acquire() as conn:
            await conn.execute(
                "UPDATE players SET username = $1 WHERE telegram_id = $2",
                new_name,
                telegram_id,
            )

    async def get_or_create_player(self, telegram_id: int, username: Optional[str]) -> dict:
        p = await self.get_player_by_telegram_id(telegram_id)
        if p:
            return p
        return await self.create_player(telegram_id, username)

    # ----- Combat stats -----
    async def get_combat_stats(self, player_id: int, for_arena: bool = False) -> dict:
        """for_arena=True: использует current_hp с восстановлением 1 HP/мин, не выше max_hp."""
        async with self.pool.acquire() as conn:
            base = await conn.fetchrow(
                """
                SELECT strength, agility, intuition, stamina, free_points, credits, experience, level,
                       current_hp, hp_updated_at, trauma_end_at
                FROM player_stats WHERE player_id = $1
                """,
                player_id,
            )
            if not base:
                return {}
            base = dict(base)
            rows = await conn.fetch(
                """
                SELECT i.bonus_str, i.bonus_hp, i.armor, i.min_damage, i.max_damage
                FROM inventory inv
                JOIN items i ON i.id = inv.item_id
                WHERE inv.player_id = $1 AND inv.is_equipped = TRUE
                """,
                player_id,
            )
            bonus_str = sum(r["bonus_str"] for r in rows)
            bonus_hp = sum(r.get("bonus_hp", 0) for r in rows)
            armor = sum(r.get("armor", 0) for r in rows)
            weapon_min = 0
            weapon_max = 0
            for r in rows:
                if r["min_damage"] or r["max_damage"]:
                    weapon_min = r["min_damage"]
                    weapon_max = r["max_damage"]
                    break
            strength = base["strength"] + bonus_str
            stamina = base["stamina"]
            level = base.get("level", 1)
            # MaxHP = 30 + (level * 5) + (stamina * 5)
            max_hp = 30 + (level * 5) + (stamina * 5)
            hp_value = max_hp
            if for_arena and base.get("current_hp") is not None and base.get("hp_updated_at"):
                import datetime
                now = datetime.datetime.now(datetime.timezone.utc)
                updated_at = base["hp_updated_at"]
                if updated_at.tzinfo is None:
                    updated_at = updated_at.replace(tzinfo=datetime.timezone.utc)
                mins = max(0, int((now - updated_at).total_seconds() / 60))
                recovered = min(mins, max_hp - base["current_hp"])
                hp_value = min(max_hp, base["current_hp"] + recovered)
                if recovered > 0:
                    await conn.execute(
                        """
                        UPDATE player_stats SET current_hp = $1, hp_updated_at = NOW() WHERE player_id = $2
                        """,
                        hp_value, player_id,
                    )
            elif for_arena and base.get("current_hp") is not None:
                hp_value = min(max_hp, base["current_hp"])
            return {
                "player_id": player_id,
                "strength": strength,
                "agility": base["agility"],
                "intuition": base["intuition"],
                "stamina": stamina,
                "hp": hp_value,
                "max_hp": max_hp,
                "armor": armor,
                "weapon_min": weapon_min,
                "weapon_max": weapon_max if weapon_max else weapon_min,
                "free_points": base["free_points"],
                "credits": base["credits"],
                "experience": base["experience"],
                "level": base["level"],
                "trauma_end_at": base.get("trauma_end_at"),
            }

    async def add_experience(self, player_id: int, exp: int) -> None:
        async with self.pool.acquire() as conn:
            await conn.execute(
                "UPDATE player_stats SET experience = experience + $1 WHERE player_id = $2",
                exp, player_id,
            )
        await self._process_level_up(player_id)

    async def _process_level_up(self, player_id: int) -> None:
        """XP Curve: exp >= (level**2)*100 → уровень +1, experience -= spent, +5 free_points."""
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT experience, level FROM player_stats WHERE player_id = $1",
                player_id,
            )
            if not row:
                return
            exp, lvl = row["experience"], row["level"]
            exp_to_next = (lvl ** 2) * 100
            if exp >= exp_to_next:
                new_exp = exp - exp_to_next
                await conn.execute(
                    "UPDATE player_stats SET level = level + 1, experience = $1, free_points = free_points + 5 WHERE player_id = $2",
                    new_exp, player_id,
                )
                await self._process_level_up(player_id)  # рекурсия на случай нескольких уровней

    async def add_credits(self, player_id: int, amount: int) -> None:
        async with self.pool.acquire() as conn:
            await conn.execute(
                "UPDATE player_stats SET credits = credits + $1 WHERE player_id = $2",
                amount, player_id,
            )

    async def set_player_current_hp(self, player_id: int, hp: int) -> None:
        """После боя на арене: сохранить текущий HP, восстановление 1 HP/мин."""
        async with self.pool.acquire() as conn:
            await conn.execute(
                "UPDATE player_stats SET current_hp = $1, hp_updated_at = NOW() WHERE player_id = $2",
                max(0, hp), player_id,
            )

    async def restore_player_hp_full(self, player_id: int) -> None:
        """Восстановить HP до 100%, снять травму."""
        async with self.pool.acquire() as conn:
            await conn.execute(
                "UPDATE player_stats SET current_hp = NULL, hp_updated_at = NULL, trauma_end_at = NULL WHERE player_id = $1",
                player_id,
            )

    async def set_trauma(self, player_id: int, minutes: int = 5) -> None:
        """Записать травму: до текущее время + minutes."""
        async with self.pool.acquire() as conn:
            await conn.execute(
                "UPDATE player_stats SET trauma_end_at = NOW() + INTERVAL '1 minute' * $1 WHERE player_id = $2",
                minutes, player_id,
            )

    async def has_trauma(self, player_id: int) -> bool:
        """True если trauma_end_at > NOW()."""
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT trauma_end_at FROM player_stats WHERE player_id = $1",
                player_id,
            )
            if not row or not row["trauma_end_at"]:
                return False
            from datetime import datetime, timezone
            end = row["trauma_end_at"]
            if end.tzinfo is None:
                end = end.replace(tzinfo=timezone.utc)
            return datetime.now(timezone.utc) < end

    async def clear_trauma(self, player_id: int) -> None:
        async with self.pool.acquire() as conn:
            await conn.execute(
                "UPDATE player_stats SET trauma_end_at = NULL WHERE player_id = $1",
                player_id,
            )

    async def add_reward(self, player_id: int, exp_gain: int, credits_gain: int) -> dict:
        async with self.pool.acquire() as conn:
            await conn.execute(
                "UPDATE player_stats SET experience = experience + $1, credits = credits + $2 WHERE player_id = $3",
                exp_gain, credits_gain, player_id
            )
            stats = await conn.fetchrow("SELECT experience, level FROM player_stats WHERE player_id = $1", player_id)
            
            current_exp = stats['experience']
            current_lvl = stats['level']
            next_lvl_exp = current_lvl * 100
            
            leveled_up = False
            if current_exp >= next_lvl_exp:
                await conn.execute(
                    "UPDATE player_stats SET level = level + 1, experience = 0, free_points = free_points + 5 WHERE player_id = $1",
                    player_id
                )
                leveled_up = True
            
            return {"leveled_up": leveled_up, "new_level": current_lvl + 1 if leveled_up else current_lvl}

    async def upgrade_stat(self, player_id: int, stat: str) -> bool:
        if stat not in ("strength", "agility", "intuition", "stamina"):
            return False
        async with self.pool.acquire() as conn:
            r = await conn.fetchrow(
                "SELECT free_points FROM player_stats WHERE player_id = $1",
                player_id,
            )
            if not r or r["free_points"] < 1:
                return False
            await conn.execute(
                f"UPDATE player_stats SET free_points = free_points - 1, {stat} = {stat} + 1 WHERE player_id = $1",
                player_id,
            )
            return True
    
    # ТОП ИГРОКОВ
    async def get_top_players(self, limit: int = 10) -> list[dict]:
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT p.username, s.level, s.experience
                FROM player_stats s
                JOIN players p ON p.id = s.player_id
                ORDER BY s.level DESC, s.experience DESC
                LIMIT $1
                """,
                limit,
            )
            return [dict(r) for r in rows]

    # ----- Items & inventory -----
    async def get_player_inventory(self, player_id: int) -> list[dict]:
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT inv.id, inv.item_id, inv.is_equipped, i.name, i.slot, i.min_damage, i.max_damage, i.bonus_str, i.bonus_hp, COALESCE(i.armor, 0) AS armor, i.price
                FROM inventory inv
                JOIN items i ON i.id = inv.item_id
                WHERE inv.player_id = $1
                ORDER BY inv.is_equipped DESC, i.slot, i.name
                """,
                player_id,
            )
            return [dict(r) for r in rows]

    async def get_item_by_id(self, item_id: int) -> Optional[dict]:
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow("SELECT * FROM items WHERE id = $1", item_id)
            return dict(row) if row else None

    async def get_item_by_name(self, name: str) -> Optional[dict]:
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow("SELECT * FROM items WHERE name = $1", name)
            return dict(row) if row else None

    async def add_item_to_inventory(self, player_id: int, item_id: int, is_equipped: bool = False) -> None:
        async with self.pool.acquire() as conn:
            await conn.execute(
                "INSERT INTO inventory (player_id, item_id, is_equipped) VALUES ($1, $2, $3)",
                player_id,
                item_id,
                is_equipped,
            )

    async def set_equipped(self, inv_id: int, player_id: int, equip: bool) -> bool:
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT inv.id, inv.item_id, i.slot FROM inventory inv JOIN items i ON i.id = inv.item_id WHERE inv.id = $1 AND inv.player_id = $2",
                inv_id,
                player_id,
            )
            if not row:
                return False
            slot = row["slot"]
            if equip:
                await conn.execute(
                    "UPDATE inventory SET is_equipped = FALSE WHERE player_id = $1 AND item_id IN (SELECT id FROM items WHERE slot = $2)",
                    player_id, slot,
                )
            await conn.execute(
                "UPDATE inventory SET is_equipped = $1 WHERE id = $2 AND player_id = $3",
                equip, inv_id, player_id,
            )
            return True

    async def remove_inventory_row(self, inv_id: int, player_id: int) -> bool:
        async with self.pool.acquire() as conn:
            r = await conn.execute(
                "DELETE FROM inventory WHERE id = $1 AND player_id = $2",
                inv_id,
                player_id,
            )
            return r == "DELETE 1"

    # ----- Potions -----
    async def get_player_potions(self, player_id: int) -> list[dict]:
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT pp.item_id, pp.quantity, i.name
                FROM player_potions pp
                JOIN items i ON i.id = pp.item_id
                WHERE pp.player_id = $1 AND pp.quantity > 0
                """,
                player_id,
            )
            return [dict(r) for r in rows]

    async def get_potion_count(self, player_id: int, item_id: int) -> int:
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT quantity FROM player_potions WHERE player_id = $1 AND item_id = $2",
                player_id, item_id,
            )
            return row["quantity"] if row else 0

    async def add_potion(self, player_id: int, item_id: int, quantity: int = 1) -> None:
        async with self.pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO player_potions (player_id, item_id, quantity)
                VALUES ($1, $2, $3)
                ON CONFLICT (player_id, item_id) DO UPDATE SET quantity = player_potions.quantity + $3
                """,
                player_id, item_id, quantity,
            )

    async def use_potion(self, player_id: int, item_id: int) -> tuple[bool, str]:
        """Выпить зелье: −1 шт., HP 100%, снять травму. Возвращает (ok, msg)."""
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT quantity FROM player_potions WHERE player_id = $1 AND item_id = $2",
                player_id, item_id,
            )
            if not row or row["quantity"] < 1:
                return False, "Нет такого зелья."
            await conn.execute(
                "UPDATE player_potions SET quantity = quantity - 1 WHERE player_id = $1 AND item_id = $2",
                player_id, item_id,
            )
        await self.restore_player_hp_full(player_id)
        await self.clear_trauma(player_id)
        return True, "Зелье выпито. HP и травма сняты."

    async def get_potion_item_id(self) -> Optional[int]:
        """ID предмета «Малое зелье жизни» (slot=potion)."""
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow("SELECT id FROM items WHERE slot = 'potion' LIMIT 1")
            return row["id"] if row else None

    # ----- Shop -----
    async def buy_item(self, player_id: int, item_id: int) -> tuple[bool, str]:
        async with self.pool.acquire() as conn:
            item = await conn.fetchrow("SELECT * FROM items WHERE id = $1", item_id)
            if not item:
                return False, "Предмет не найден."
            stats = await conn.fetchrow("SELECT credits FROM player_stats WHERE player_id = $1", player_id)
            if stats["credits"] < item["price"]:
                return False, "Недостаточно кредитов."
            await conn.execute(
                "UPDATE player_stats SET credits = credits - $1 WHERE player_id = $2",
                item["price"], player_id,
            )
            if item["slot"] == "potion":
                await conn.execute(
                    """
                    INSERT INTO player_potions (player_id, item_id, quantity)
                    VALUES ($1, $2, 1)
                    ON CONFLICT (player_id, item_id) DO UPDATE SET quantity = player_potions.quantity + 1
                    """,
                    player_id, item_id,
                )
            else:
                await conn.execute("INSERT INTO inventory (player_id, item_id) VALUES ($1, $2)", player_id, item_id)
            return True, f"Куплено: {item['name']}."
    
    async def sell_item(self, player_id: int, inv_id: int) -> tuple[bool, str, int]:
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT inv.id, inv.is_equipped, i.name, i.price
                FROM inventory inv JOIN items i ON i.id = inv.item_id
                WHERE inv.id = $1 AND inv.player_id = $2
                """,
                inv_id, player_id,
            )
            if not row: return False, "Предмет не найден.", 0
            price = max(1, row["price"] // 2)
            await conn.execute("DELETE FROM inventory WHERE id = $1 AND player_id = $2", inv_id, player_id)
            await conn.execute("UPDATE player_stats SET credits = credits + $1 WHERE player_id = $2", price, player_id)
            return True, f"Продано: {row['name']}. +{price} кр.", price

    async def get_shop_items(self) -> list[dict]:
        async with self.pool.acquire() as conn:
            rows = await conn.fetch("SELECT * FROM items ORDER BY price")
            return [dict(r) for r in rows]

    # ----- System balance -----
    async def get_system_commission(self) -> int:
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow("SELECT total_commission FROM system_balance ORDER BY id LIMIT 1")
            return row["total_commission"] if row else 0

    async def add_commission(self, amount: int) -> None:
        async with self.pool.acquire() as conn:
            await conn.execute(
                "UPDATE system_balance SET total_commission = total_commission + $1 WHERE id = (SELECT id FROM system_balance ORDER BY id LIMIT 1)",
                amount,
            )

    async def reset_commission(self) -> None:
        async with self.pool.acquire() as conn:
            await conn.execute("UPDATE system_balance SET total_commission = 0 WHERE id = (SELECT id FROM system_balance ORDER BY id LIMIT 1)")

    async def get_players_count(self) -> int:
        async with self.pool.acquire() as conn:
            return await conn.fetchval("SELECT COUNT(*) FROM players") or 0

    async def get_system_balance(self) -> int:
        """Алиас: банк системы (total_commission)."""
        return await self.get_system_commission()

    async def reset_system_balance(self) -> None:
        """Алиас: обнулить кассу."""
        await self.reset_commission()

    async def get_total_players_count(self) -> int:
        """Алиас: всего игроков."""
        return await self.get_players_count()

    async def get_battles_count(self) -> int:
        async with self.pool.acquire() as conn:
            return await conn.fetchval("SELECT COUNT(*) FROM battles") or 0

    async def get_top_rich(self, limit: int = 3) -> list[dict]:
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT p.username, s.credits
                FROM player_stats s
                JOIN players p ON p.id = s.player_id
                ORDER BY s.credits DESC
                LIMIT $1
                """,
                limit,
            )
            return [dict(r) for r in rows]

    # ----- Shadow fight (PvE vs AI) -----
    async def get_shadow_fight(self, fight_id: int) -> Optional[dict]:
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT id, player_id, shadow_hp, player_hp, round, is_finished, COALESCE(potion_used, FALSE) AS potion_used FROM shadow_fights WHERE id = $1",
                fight_id,
            )
            return dict(row) if row else None

    async def get_active_shadow_fight(self, player_id: int) -> Optional[dict]:
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT id, player_id, shadow_hp, player_hp, round, is_finished, COALESCE(potion_used, FALSE) AS potion_used
                FROM shadow_fights
                WHERE player_id = $1 AND is_finished = FALSE
                ORDER BY id DESC LIMIT 1
                """,
                player_id,
            )
            return dict(row) if row else None

    async def has_active_fight(self, player_id: int) -> bool:
        """True если у игрока есть активный бой (shadow или arena)."""
        shadow = await self.get_active_shadow_fight(player_id)
        if shadow:
            return True
        arena_b = await self.get_active_battle_for_player(player_id)
        return arena_b is not None

    async def start_shadow_fight(self, player_id: int) -> Optional[dict]:
        """Создаёт бой против Тени. Статы Тени = статы игрока, HP Тени фиксировано (честный тест)."""
        stats = await self.get_combat_stats(player_id)
        if not stats:
            return None
        player_hp = stats["hp"]
        shadow_hp = 40  # фиксированное HP для честного теста
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                INSERT INTO shadow_fights (player_id, shadow_hp, player_hp, round, is_finished, potion_used)
                VALUES ($1, $2, $3, 1, FALSE, FALSE)
                RETURNING id, player_id, shadow_hp, player_hp, round, is_finished
                """,
                player_id, shadow_hp, player_hp,
            )
            return dict(row) if row else None

    async def use_potion_shadow(self, fight_id: int, player_id: int) -> tuple[bool, int, str]:
        """Free Action: зелье 1 раз за бой, не тратит ход. Восстанавливает 25% MaxHP (округление вверх)."""
        fight = await self.get_shadow_fight(fight_id)
        if not fight or fight["is_finished"]:
            return False, 0, "Бой завершён."
        if fight.get("potion_used"):
            return False, 0, "Вы уже использовали эликсир в этом бою!"
        potion_id = await self.get_potion_item_id()
        if not potion_id or await self.get_potion_count(player_id, potion_id) < 1:
            return False, 0, "Нет зелий."
        stats = await self.get_combat_stats(player_id)
        max_hp = stats.get("max_hp", 40)
        import math
        heal = math.ceil(max_hp * 0.25)
        current_hp = fight["player_hp"]
        new_hp = min(max_hp, current_hp + heal)
        async with self.pool.acquire() as conn:
            await conn.execute(
                "UPDATE player_potions SET quantity = quantity - 1 WHERE player_id = $1 AND item_id = $2 AND quantity >= 1",
                player_id, potion_id,
            )
            await conn.execute(
                "UPDATE shadow_fights SET player_hp = $1, potion_used = TRUE WHERE id = $2",
                new_hp, fight_id,
            )
        return True, new_hp, f"Зелье выпито. +{heal} HP (25% от макс.)."

    async def process_shadow_turn(
        self, fight_id: int, player_atk: int, player_blk: int
    ) -> tuple[Optional[dict], Optional[dict], list[str], bool, bool]:
        """
        ИИ Тени выбирает рандомные зоны. Зелье — Free Action в handler (use_potion_shadow), сюда не передаётся.
        """
        import random
        fight = await self.get_shadow_fight(fight_id)
        if not fight or fight["is_finished"]:
            return None, None, [], False, False
        player_id = fight["player_id"]
        stats = await self.get_combat_stats(player_id)
        if not stats:
            return None, None, [], False, False

        player_hp = fight["player_hp"]
        shadow_atk = random.randint(1, 3)
        shadow_blk = random.randint(1, 3)
        from services.game_math import BattleMath, CombatStats
        wmin, wmax = stats.get("weapon_min", 1), stats.get("weapon_max", 2)
        lvl, arm = stats.get("level", 1), stats.get("armor", 0)
        max_hp = stats.get("max_hp", 40)
        player_combat: CombatStats = {
            "strength": stats["strength"],
            "agility": stats["agility"],
            "intuition": stats["intuition"],
            "stamina": stats["stamina"],
            "hp": player_hp,
            "max_hp": max_hp,
            "weapon_min": wmin,
            "weapon_max": wmax,
            "armor": arm,
            "level": lvl,
        }
        # Тень = зеркало статов игрока, то же оружие и броня
        shadow_combat: CombatStats = {
            "strength": stats["strength"],
            "agility": stats["agility"],
            "intuition": stats["intuition"],
            "stamina": stats["stamina"],
            "hp": fight["shadow_hp"],
            "max_hp": max_hp,
            "weapon_min": wmin,
            "weapon_max": wmax,
            "armor": arm,
            "level": lvl,
        }
        new_player_hp, new_shadow_hp, log_lines = BattleMath.resolve_round(
            player_combat, shadow_combat,
            player_atk, player_blk,
            shadow_atk, shadow_blk,
            name1="Вы", name2="Тень",
        )
        is_finished = new_player_hp <= 0 or new_shadow_hp <= 0
        async with self.pool.acquire() as conn:
            await conn.execute(
                """
                UPDATE shadow_fights
                SET shadow_hp = $1, player_hp = $2, round = round + 1, is_finished = $3
                WHERE id = $4
                """,
                max(0, new_shadow_hp), max(0, new_player_hp), is_finished, fight_id,
            )
        updated = await self.get_shadow_fight(fight_id)
        player_won = is_finished and new_shadow_hp <= 0
        old_level = stats.get("level", 1)
        # Награды: победа 20 + Lvl*5 XP, 10 + Lvl*2 золота; поражение 50% XP, 30% золота
        xp_win = 20 + (old_level * 5)
        gold_win = 10 + (old_level * 2)
        if player_won:
            await self.add_credits(player_id, gold_win)
            await self.add_experience(player_id, xp_win)
        else:
            if is_finished:
                await self.add_credits(player_id, max(1, int(gold_win * 0.3)))
                await self.add_experience(player_id, max(1, int(xp_win * 0.5)))
        if is_finished:
            await self.restore_player_hp_full(player_id)
        new_stats = await self.get_combat_stats(player_id)
        leveled_up = (new_stats.get("level", 1) or 1) > old_level
        return updated, stats, log_lines, player_won, leveled_up

    async def finish_shadow_fight(self, fight_id: int) -> None:
        async with self.pool.acquire() as conn:
            await conn.execute("UPDATE shadow_fights SET is_finished = TRUE WHERE id = $1", fight_id)

    # ----- PvP Arena -----
    async def arena_join_queue(self, player_id: int, stake: int = 100) -> tuple[str, Optional[int], str]:
        """Возвращает (status, battle_id, message). stake — ставка с каждого (100 кр.)."""
        stats = await self.get_combat_stats(player_id)
        if not stats or stats.get("credits", 0) < stake:
            return "no_credits", None, "Недостаточно кредитов для ставки (нужно {} кр.).".format(stake)
        async with self.pool.acquire() as conn:
            existing = await conn.fetchval("SELECT 1 FROM arena_queue WHERE player_id = $1", player_id)
            if existing:
                return "waiting", None, "Вы уже в очереди."
            other = await conn.fetchrow("SELECT player_id FROM arena_queue WHERE player_id != $1 LIMIT 1", player_id)
            if not other:
                await conn.execute(
                    "INSERT INTO arena_queue (player_id) VALUES ($1) ON CONFLICT (player_id) DO NOTHING",
                    player_id,
                )
                return "waiting", None, "Ожидайте соперника."
            other_id = other["player_id"]
            other_stats = await self.get_combat_stats(other_id)
            if not other_stats or other_stats.get("credits", 0) < stake:
                await conn.execute("DELETE FROM arena_queue WHERE player_id = $1", other_id)
                return "waiting", None, "Соперник не прошёл проверку ставки. Вы в очереди."
            await conn.execute("DELETE FROM arena_queue WHERE player_id = $1", other_id)
            await conn.execute(
                "UPDATE player_stats SET credits = credits - $1 WHERE player_id = $2",
                stake, player_id,
            )
            await conn.execute(
                "UPDATE player_stats SET credits = credits - $1 WHERE player_id = $2",
                stake, other_id,
            )
            s1, s2 = await self.get_combat_stats(player_id, for_arena=True), await self.get_combat_stats(other_id, for_arena=True)
            row = await conn.fetchrow(
                """
                INSERT INTO battles (player1_id, player2_id, player1_hp, player2_hp, stake)
                VALUES ($1, $2, $3, $4, $5)
                RETURNING id
                """,
                player_id, other_id, s1["hp"], s2["hp"], stake,
            )
            return "matched", row["id"], "Бой начат!"

    async def arena_leave_queue(self, player_id: int) -> None:
        async with self.pool.acquire() as conn:
            await conn.execute("DELETE FROM arena_queue WHERE player_id = $1", player_id)

    async def get_battle(self, battle_id: int) -> Optional[dict]:
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT b.*, p1.username AS p1_name, p2.username AS p2_name
                FROM battles b
                JOIN players p1 ON b.player1_id = p1.id
                JOIN players p2 ON b.player2_id = p2.id
                WHERE b.id = $1
                """, battle_id
            )
            return dict(row) if row else None

    async def get_active_battle_for_player(self, player_id: int) -> Optional[dict]:
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT b.*, p1.username AS p1_name, p2.username AS p2_name
                FROM battles b
                JOIN players p1 ON b.player1_id = p1.id
                JOIN players p2 ON b.player2_id = p2.id
                WHERE (player1_id = $1 OR player2_id = $1) AND is_finished = FALSE
                ORDER BY id DESC LIMIT 1
                """, player_id
            )
            return dict(row) if row else None

    async def set_battle_message_id(self, battle_id: int, player_id: int, msg_id: int) -> None:
        async with self.pool.acquire() as conn:
            battle = await self.get_battle(battle_id)
            if not battle: return
            col = "p1_msg_id" if battle["player1_id"] == player_id else "p2_msg_id"
            await conn.execute(f"UPDATE battles SET {col} = $1 WHERE id = $2", msg_id, battle_id)

    async def make_move(self, battle_id: int, player_id: int, atk: int, blk: int) -> tuple[bool, str]:
        battle = await self.get_battle(battle_id)
        if not battle or battle["is_finished"]:
            return False, "Бой завершён."
        col_atk, col_blk = ("p1_attack_zone", "p1_block_zone") if battle["player1_id"] == player_id else ("p2_attack_zone", "p2_block_zone")
        if battle[col_atk] is not None:
            return False, "Вы уже сделали ход."
        async with self.pool.acquire() as conn:
            await conn.execute(f"UPDATE battles SET {col_atk} = $1, {col_blk} = $2 WHERE id = $3", atk, blk, battle_id)
        return True, "Ход принят."

    async def make_heal_arena(self, battle_id: int, player_id: int) -> tuple[bool, str]:
        """Free Action: зелье 1 раз за бой, не тратит ход. 25% MaxHP (округление вверх). Не меняет attack/block."""
        battle = await self.get_battle(battle_id)
        if not battle or battle["is_finished"]:
            return False, "Бой завершён."
        col_hp = "player1_hp" if battle["player1_id"] == player_id else "player2_hp"
        col_potion = "p1_potion_used" if battle["player1_id"] == player_id else "p2_potion_used"
        if battle.get(col_potion):
            return False, "Вы уже использовали эликсир в этом бою!"
        potion_id = await self.get_potion_item_id()
        if not potion_id or await self.get_potion_count(player_id, potion_id) < 1:
            return False, "Нет зелий."
        stats = await self.get_combat_stats(battle["player1_id"] if battle["player1_id"] == player_id else battle["player2_id"])
        max_hp = stats.get("max_hp", 40)
        import math
        heal = math.ceil(max_hp * 0.25)
        current_hp = battle[col_hp]
        new_hp = min(max_hp, current_hp + heal)
        async with self.pool.acquire() as conn:
            await conn.execute(
                "UPDATE player_potions SET quantity = quantity - 1 WHERE player_id = $1 AND item_id = $2 AND quantity >= 1",
                player_id, potion_id,
            )
            await conn.execute(
                f"UPDATE battles SET {col_hp} = $1, {col_potion} = TRUE WHERE id = $2",
                new_hp, battle_id,
            )
        return True, f"Зелье выпито. +{heal} HP (25% от макс.). Выберите атаку и защиту."

    async def check_round_ready(self, battle_id: int) -> bool:
        b = await self.get_battle(battle_id)
        return all(v is not None for v in [b["p1_attack_zone"], b["p2_attack_zone"]])

    async def resolve_round_and_advance(self, battle_id: int, hp1: int, hp2: int) -> dict:
        async with self.pool.acquire() as conn:
            is_fin = hp1 <= 0 or hp2 <= 0
            win_id = None
            if hp1 <= 0: win_id = (await self.get_battle(battle_id))["player2_id"]
            elif hp2 <= 0: win_id = (await self.get_battle(battle_id))["player1_id"]
            
            await conn.execute(
                """
                UPDATE battles SET player1_hp = $1, player2_hp = $2, 
                p1_attack_zone = NULL, p1_block_zone = NULL, p2_attack_zone = NULL, p2_block_zone = NULL,
                round_number = round_number + 1, is_finished = $3, winner_id = $4
                WHERE id = $5
                """, max(0, hp1), max(0, hp2), is_fin, win_id, battle_id
            )
            return await self.get_battle(battle_id)

    async def resolve_arena_winner(self, battle_id: int, winner_id: int, stake: int) -> None:
        """Банк = stake * 2. 10% в total_commission, 90% победителю."""
        bank = stake * 2
        commission = int(bank * 0.10)
        winner_gain = bank - commission
        async with self.pool.acquire() as conn:
            await conn.execute(
                "UPDATE player_stats SET credits = credits + $1 WHERE player_id = $2",
                winner_gain, winner_id,
            )
        await self.add_commission(commission)

    async def surrender_battle(self, battle_id: int, loser_id: int) -> dict:
        """Завершает бой сдачей. Сохраняет current_hp обоим (травмы арены)."""
        battle = await self.get_battle(battle_id)
        if not battle:
            return None
        winner_id = battle["player2_id"] if battle["player1_id"] == loser_id else battle["player1_id"]
        stake = battle.get("stake") or 0
        async with self.pool.acquire() as conn:
            await conn.execute("UPDATE battles SET is_finished = TRUE, winner_id = $1 WHERE id = $2", winner_id, battle_id)
        if stake > 0:
            await self.resolve_arena_winner(battle_id, winner_id, stake)
        await self.set_player_current_hp(battle["player1_id"], battle["player1_hp"])
        await self.set_player_current_hp(battle["player2_id"], battle["player2_hp"])
        await self.set_trauma(loser_id, 5)
        return await self.get_battle(battle_id)

    async def close_stale_battles(self, minutes: int = 30) -> None:
        """Автоматически завершает бои, которые висят дольше N минут."""
        async with self.pool.acquire() as conn:
            await conn.execute(f"UPDATE battles SET is_finished = TRUE WHERE is_finished = FALSE AND created_at < NOW() - INTERVAL '{minutes} minutes'")
            await conn.execute(f"DELETE FROM arena_queue WHERE joined_at < NOW() - INTERVAL '{minutes} minutes'")

db = Database()