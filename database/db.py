"""
Database layer: PostgreSQL via asyncpg.
Creates tables on init, provides all SQL operations.
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
            # player_stats
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS player_stats (
                    player_id INTEGER PRIMARY KEY REFERENCES players(id) ON DELETE CASCADE,
                    strength INTEGER NOT NULL DEFAULT 3,
                    agility INTEGER NOT NULL DEFAULT 3,
                    intuition INTEGER NOT NULL DEFAULT 3,
                    stamina INTEGER NOT NULL DEFAULT 3,
                    free_points INTEGER NOT NULL DEFAULT 0,
                    credits INTEGER NOT NULL DEFAULT 0,
                    experience INTEGER NOT NULL DEFAULT 0,
                    level INTEGER NOT NULL DEFAULT 1
                )
            """)
            # items
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS items (
                    id SERIAL PRIMARY KEY,
                    name TEXT NOT NULL,
                    slot TEXT NOT NULL,
                    min_damage INTEGER NOT NULL DEFAULT 0,
                    max_damage INTEGER NOT NULL DEFAULT 0,
                    bonus_str INTEGER NOT NULL DEFAULT 0,
                    bonus_hp INTEGER NOT NULL DEFAULT 0,
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
            # PvP battles
            # Добавляем колонки p1_msg_id и p2_msg_id для редактирования сообщений
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
                    p2_msg_id INTEGER
                )
            """)
            
            # Миграция: если таблица уже была, добавляем колонки для редактирования
            try:
                await conn.execute("ALTER TABLE battles ADD COLUMN IF NOT EXISTS p1_msg_id INTEGER")
                await conn.execute("ALTER TABLE battles ADD COLUMN IF NOT EXISTS p2_msg_id INTEGER")
            except Exception:
                pass

            # Arena queue
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS arena_queue (
                    player_id INTEGER PRIMARY KEY REFERENCES players(id) ON DELETE CASCADE,
                    joined_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
                )
            """)
        await self.add_initial_items()
        logger.info("Database init complete")

    async def add_initial_items(self) -> None:
        async with self.pool.acquire() as conn:
            n = await conn.fetchval("SELECT COUNT(*) FROM items")
            if n and n > 0:
                return
            await conn.execute("""
                INSERT INTO items (name, slot, min_damage, max_damage, bonus_str, bonus_hp, price)
                VALUES
                    ('Нож', 'weapon', 1, 3, 0, 0, 10),
                    ('Меч', 'weapon', 3, 6, 0, 0, 25),
                    ('Броня', 'chest', 0, 0, 0, 15, 30),
                    ('Ржавый нож', 'weapon', 1, 2, 0, 0, 3)
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
                """
                INSERT INTO player_stats (player_id)
                VALUES ($1)
                """,
                pid,
            )
            return dict(row)

    async def get_or_create_player(self, telegram_id: int, username: Optional[str]) -> dict:
        p = await self.get_player_by_telegram_id(telegram_id)
        if p:
            return p
        return await self.create_player(telegram_id, username)

    # ----- Combat stats (base + equipment bonuses) -----
    async def get_combat_stats(self, player_id: int) -> dict:
        async with self.pool.acquire() as conn:
            base = await conn.fetchrow(
                """
                SELECT strength, agility, intuition, stamina, free_points, credits, experience, level
                FROM player_stats WHERE player_id = $1
                """,
                player_id,
            )
            if not base:
                return {}
            base = dict(base)
            rows = await conn.fetch(
                """
                SELECT i.bonus_str, i.bonus_hp, i.min_damage, i.max_damage
                FROM inventory inv
                JOIN items i ON i.id = inv.item_id
                WHERE inv.player_id = $1 AND inv.is_equipped = TRUE
                """,
                player_id,
            )
            bonus_str = sum(r["bonus_str"] for r in rows)
            bonus_hp = sum(r["bonus_hp"] for r in rows)
            weapon_min = 0
            weapon_max = 0
            for r in rows:
                if r["min_damage"] or r["max_damage"]:
                    weapon_min = r["min_damage"]
                    weapon_max = r["max_damage"]
                    break
            strength = base["strength"] + bonus_str
            stamina = base["stamina"]
            hp_base = stamina * 5 + bonus_hp
            return {
                "player_id": player_id,
                "strength": strength,
                "agility": base["agility"],
                "intuition": base["intuition"],
                "stamina": stamina,
                "hp": hp_base,
                "bonus_hp": bonus_hp,
                "weapon_min": weapon_min,
                "weapon_max": weapon_max if weapon_max else weapon_min,
                "free_points": base["free_points"],
                "credits": base["credits"],
                "experience": base["experience"],
                "level": base["level"],
            }

    async def add_experience(self, player_id: int, exp: int) -> None:
        async with self.pool.acquire() as conn:
            await conn.execute(
                "UPDATE player_stats SET experience = experience + $1 WHERE player_id = $2",
                exp,
                player_id,
            )
            row = await conn.fetchrow(
                "SELECT experience, level, free_points FROM player_stats WHERE player_id = $1",
                player_id,
            )
            if row:
                total_exp = row["experience"]
                new_level = 1 + total_exp // 100
                extra_points = (new_level - row["level"]) * 2
                await conn.execute(
                    """
                    UPDATE player_stats
                    SET level = $1, free_points = free_points + $2
                    WHERE player_id = $3
                    """,
                    new_level,
                    max(0, extra_points),
                    player_id,
                )

    async def add_credits(self, player_id: int, amount: int) -> None:
        async with self.pool.acquire() as conn:
            await conn.execute(
                "UPDATE player_stats SET credits = credits + $1 WHERE player_id = $2",
                amount,
                player_id,
            )

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
    
    # === НОВАЯ ФУНКЦИЯ ДЛЯ ТОПА ===
    async def get_top_players(self, limit: int = 10) -> list[dict]:
        """Возвращает список топ игроков по уровню и опыту."""
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
                SELECT inv.id, inv.item_id, inv.is_equipped, i.name, i.slot, i.min_damage, i.max_damage, i.bonus_str, i.bonus_hp, i.price
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
                    """
                    UPDATE inventory SET is_equipped = FALSE
                    WHERE player_id = $1 AND item_id IN (SELECT id FROM items WHERE slot = $2)
                    """,
                    player_id,
                    slot,
                )
            await conn.execute(
                "UPDATE inventory SET is_equipped = $1 WHERE id = $2 AND player_id = $3",
                equip,
                inv_id,
                player_id,
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

    # ----- Shop -----
    async def buy_item(self, player_id: int, item_id: int) -> tuple[bool, str]:
        async with self.pool.acquire() as conn:
            item = await conn.fetchrow("SELECT * FROM items WHERE id = $1", item_id)
            if not item:
                return False, "Предмет не найден."
            stats = await conn.fetchrow(
                "SELECT credits FROM player_stats WHERE player_id = $1",
                player_id,
            )
            if not stats or stats["credits"] < item["price"]:
                return False, "Недостаточно кредитов."
            await conn.execute(
                "UPDATE player_stats SET credits = credits - $1 WHERE player_id = $2",
                item["price"],
                player_id,
            )
            await conn.execute(
                "INSERT INTO inventory (player_id, item_id, is_equipped) VALUES ($1, $2, FALSE)",
                player_id,
                item_id,
            )
            return True, f"Куплено: {item['name']}."

    async def sell_item(self, player_id: int, inv_id: int) -> tuple[bool, str, int]:
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT inv.id, inv.is_equipped, i.name, i.price
                FROM inventory inv JOIN items i ON i.id = inv.item_id
                WHERE inv.id = $1 AND inv.player_id = $2
                """,
                inv_id,
                player_id,
            )
            if not row:
                return False, "Предмет не найден.", 0
            price = max(1, row["price"] // 2)
            await conn.execute("DELETE FROM inventory WHERE id = $1 AND player_id = $2", inv_id, player_id)
            await conn.execute(
                "UPDATE player_stats SET credits = credits + $1 WHERE player_id = $2",
                price,
                player_id,
            )
            return True, f"Продано: {row['name']}. +{price} кр.", price

    async def get_shop_items(self) -> list[dict]:
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT id, name, slot, min_damage, max_damage, bonus_str, bonus_hp, price FROM items ORDER BY price"
            )
            return [dict(r) for r in rows]

    # ----- PvP Arena -----
    async def arena_join_queue(self, player_id: int) -> tuple[str, Optional[int]]:
        async with self.pool.acquire() as conn:
            existing = await conn.fetchval("SELECT 1 FROM arena_queue WHERE player_id = $1", player_id)
            if existing:
                return "waiting", None
            other = await conn.fetchrow(
                "SELECT player_id FROM arena_queue WHERE player_id != $1 LIMIT 1",
                player_id,
            )
            if not other:
                await conn.execute(
                    "INSERT INTO arena_queue (player_id) VALUES ($1) ON CONFLICT (player_id) DO NOTHING",
                    player_id,
                )
                return "waiting", None
            other_id = other["player_id"]
            await conn.execute("DELETE FROM arena_queue WHERE player_id = $1", other_id)
            stats1 = await self.get_combat_stats(player_id)
            stats2 = await self.get_combat_stats(other_id)
            hp1 = stats1.get("hp", 15)
            hp2 = stats2.get("hp", 15)
            row = await conn.fetchrow(
                """
                INSERT INTO battles (player1_id, player2_id, player1_hp, player2_hp)
                VALUES ($1, $2, $3, $4)
                RETURNING id
                """,
                player_id,
                other_id,
                hp1,
                hp2,
            )
            return "matched", row["id"]

    async def arena_leave_queue(self, player_id: int) -> None:
        async with self.pool.acquire() as conn:
            await conn.execute("DELETE FROM arena_queue WHERE player_id = $1", player_id)

    # ОБНОВЛЕН: теперь тянет имена игроков (username) и ID сообщений (msg_id)
    async def get_battle(self, battle_id: int) -> Optional[dict]:
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT b.id, b.player1_id, b.player2_id, b.player1_hp, b.player2_hp, b.round_number,
                       b.p1_attack_zone, b.p1_block_zone, b.p2_attack_zone, b.p2_block_zone, 
                       b.is_finished, b.winner_id, b.p1_msg_id, b.p2_msg_id,
                       p1.username AS p1_name, p2.username AS p2_name
                FROM battles b
                JOIN players p1 ON b.player1_id = p1.id
                JOIN players p2 ON b.player2_id = p2.id
                WHERE b.id = $1
                """,
                battle_id,
            )
            return dict(row) if row else None

    # ОБНОВЛЕН: теперь тянет имена игроков (username) и ID сообщений
    async def get_active_battle_for_player(self, player_id: int) -> Optional[dict]:
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT b.id, b.player1_id, b.player2_id, b.player1_hp, b.player2_hp, b.round_number,
                       b.p1_attack_zone, b.p1_block_zone, b.p2_attack_zone, b.p2_block_zone, 
                       b.is_finished, b.winner_id, b.p1_msg_id, b.p2_msg_id,
                       p1.username AS p1_name, p2.username AS p2_name
                FROM battles b
                JOIN players p1 ON b.player1_id = p1.id
                JOIN players p2 ON b.player2_id = p2.id
                WHERE (b.player1_id = $1 OR b.player2_id = $1) AND b.is_finished = FALSE
                ORDER BY b.id DESC LIMIT 1
                """,
                player_id,
            )
            return dict(row) if row else None

    # НОВАЯ ФУНКЦИЯ: сохранить ID сообщения для редактирования
    async def set_battle_message_id(self, battle_id: int, player_id: int, message_id: int) -> None:
        battle = await self.get_battle(battle_id)
        if not battle:
            return
        async with self.pool.acquire() as conn:
            if battle["player1_id"] == player_id:
                await conn.execute("UPDATE battles SET p1_msg_id = $1 WHERE id = $2", message_id, battle_id)
            elif battle["player2_id"] == player_id:
                await conn.execute("UPDATE battles SET p2_msg_id = $1 WHERE id = $2", message_id, battle_id)

    async def make_move(self, battle_id: int, player_id: int, attack_zone: int, block_zone: int) -> tuple[bool, str]:
        battle = await self.get_battle(battle_id)
        if not battle or battle["is_finished"]:
            return False, "Бой завершён."
        if battle["player1_id"] == player_id:
            if battle["p1_attack_zone"] is not None:
                return False, "Вы уже сделали ход в этом раунде."
            async with self.pool.acquire() as conn:
                await conn.execute(
                    "UPDATE battles SET p1_attack_zone = $1, p1_block_zone = $2 WHERE id = $3",
                    attack_zone,
                    block_zone,
                    battle_id,
                )
            return True, "Ход принят."
        elif battle["player2_id"] == player_id:
            if battle["p2_attack_zone"] is not None:
                return False, "Вы уже сделали ход в этом раунде."
            async with self.pool.acquire() as conn:
                await conn.execute(
                    "UPDATE battles SET p2_attack_zone = $1, p2_block_zone = $2 WHERE id = $3",
                    attack_zone,
                    block_zone,
                    battle_id,
                )
            return True, "Ход принят."
        return False, "Вы не участник этого боя."

    async def check_round_ready(self, battle_id: int) -> bool:
        battle = await self.get_battle(battle_id)
        if not battle:
            return False
        return (
            battle["p1_attack_zone"] is not None
            and battle["p1_block_zone"] is not None
            and battle["p2_attack_zone"] is not None
            and battle["p2_block_zone"] is not None
        )

    async def resolve_round_and_advance(self, battle_id: int, new_p1_hp: int, new_p2_hp: int) -> dict:
        async with self.pool.acquire() as conn:
            winner_id = None
            is_finished = False
            if new_p1_hp <= 0:
                winner_id = await conn.fetchval("SELECT player2_id FROM battles WHERE id = $1", battle_id)
                is_finished = True
            elif new_p2_hp <= 0:
                winner_id = await conn.fetchval("SELECT player1_id FROM battles WHERE id = $1", battle_id)
                is_finished = True
            await conn.execute(
                """
                UPDATE battles
                SET player1_hp = $1, player2_hp = $2,
                    p1_attack_zone = NULL, p1_block_zone = NULL, p2_attack_zone = NULL, p2_block_zone = NULL,
                    round_number = round_number + 1,
                    is_finished = $3, winner_id = $4
                WHERE id = $5
                """,
                max(0, new_p1_hp),
                max(0, new_p2_hp),
                is_finished,
                winner_id,
                battle_id,
            )
            return await self.get_battle(battle_id)

    async def clear_round_moves(self, battle_id: int) -> None:
        async with self.pool.acquire() as conn:
            await conn.execute(
                """
                UPDATE battles
                SET p1_attack_zone = NULL, p1_block_zone = NULL, p2_attack_zone = NULL, p2_block_zone = NULL
                WHERE id = $1
                """,
                battle_id,
            )

db = Database()