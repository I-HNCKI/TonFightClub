"""
Database layer: PostgreSQL via asyncpg.
Подключение только через DB_URL из .env (python-dotenv).
"""
import os
import logging
from typing import Optional

from dotenv import load_dotenv
import asyncpg
from asyncpg import Pool

load_dotenv()

logger = logging.getLogger(__name__)

# Матрица классов: оружие (rogue/tank/warrior) и броня (head/body/legs) по уровням 1–3, зелья
_INITIAL_ITEMS = [
    # Оружие Lvl 1 (урон 2–5)
    {"name": "Ржавый заточенный штырь", "slot": "weapon", "class_type": "rogue", "min_damage": 2, "max_damage": 5, "bonus_str": 0, "bonus_hp": 0, "armor": 0, "price": 1, "min_level": 1},
    {"name": "Дубовая палка", "slot": "weapon", "class_type": "tank", "min_damage": 2, "max_damage": 5, "bonus_str": 0, "bonus_hp": 0, "armor": 0, "price": 1, "min_level": 1},
    {"name": "Старый кухонный тесак", "slot": "weapon", "class_type": "warrior", "min_damage": 2, "max_damage": 5, "bonus_str": 0, "bonus_hp": 0, "armor": 0, "price": 1, "min_level": 1},
    # Оружие Lvl 2 (4–8)
    {"name": "Костяной нож", "slot": "weapon", "class_type": "rogue", "min_damage": 4, "max_damage": 8, "bonus_str": 0, "bonus_hp": 0, "armor": 0, "price": 2, "min_level": 2},
    {"name": "Окованная дубина", "slot": "weapon", "class_type": "tank", "min_damage": 4, "max_damage": 8, "bonus_str": 0, "bonus_hp": 0, "armor": 0, "price": 2, "min_level": 2},
    {"name": "Короткий гладиус", "slot": "weapon", "class_type": "warrior", "min_damage": 4, "max_damage": 8, "bonus_str": 0, "bonus_hp": 0, "armor": 0, "price": 2, "min_level": 2},
    # Оружие Lvl 3 (7–12)
    {"name": "Пара стилетов", "slot": "weapon", "class_type": "rogue", "min_damage": 7, "max_damage": 12, "bonus_str": 0, "bonus_hp": 0, "armor": 0, "price": 3, "min_level": 3},
    {"name": "Каменный топор", "slot": "weapon", "class_type": "tank", "min_damage": 7, "max_damage": 12, "bonus_str": 0, "bonus_hp": 0, "armor": 0, "price": 3, "min_level": 3},
    {"name": "Острое копье", "slot": "weapon", "class_type": "warrior", "min_damage": 7, "max_damage": 12, "bonus_str": 0, "bonus_hp": 0, "armor": 0, "price": 3, "min_level": 3},
    # Броня Lvl 1 (голова/тело/ноги, суммарно ~2%)
    {"name": "Тканевая бандана", "slot": "head", "class_type": "all", "min_damage": 0, "max_damage": 0, "bonus_str": 0, "bonus_hp": 0, "armor": 0, "price": 1, "min_level": 1},
    {"name": "Рваная рубаха", "slot": "body", "class_type": "all", "min_damage": 0, "max_damage": 0, "bonus_str": 0, "bonus_hp": 0, "armor": 1, "price": 1, "min_level": 1},
    {"name": "Обмотки", "slot": "legs", "class_type": "all", "min_damage": 0, "max_damage": 0, "bonus_str": 0, "bonus_hp": 0, "armor": 0, "price": 1, "min_level": 1},
    # Броня Lvl 2 (~5%)
    {"name": "Кожаная шапка", "slot": "head", "class_type": "all", "min_damage": 0, "max_damage": 0, "bonus_str": 0, "bonus_hp": 0, "armor": 1, "price": 2, "min_level": 2},
    {"name": "Кожаный жилет", "slot": "body", "class_type": "all", "min_damage": 0, "max_damage": 0, "bonus_str": 0, "bonus_hp": 0, "armor": 1, "price": 2, "min_level": 2},
    {"name": "Сандалии", "slot": "legs", "class_type": "all", "min_damage": 0, "max_damage": 0, "bonus_str": 0, "bonus_hp": 0, "armor": 1, "price": 2, "min_level": 2},
    # Броня Lvl 3 (~10%)
    {"name": "Медный шлем", "slot": "head", "class_type": "all", "min_damage": 0, "max_damage": 0, "bonus_str": 0, "bonus_hp": 0, "armor": 2, "price": 3, "min_level": 3},
    {"name": "Стеганая куртка", "slot": "body", "class_type": "all", "min_damage": 0, "max_damage": 0, "bonus_str": 0, "bonus_hp": 0, "armor": 2, "price": 3, "min_level": 3},
    {"name": "Кожаные сапоги", "slot": "legs", "class_type": "all", "min_damage": 0, "max_damage": 0, "bonus_str": 0, "bonus_hp": 0, "armor": 2, "price": 3, "min_level": 3},
    # Зелья
    {"name": "Бинты", "slot": "potion", "class_type": "all", "min_damage": 0, "max_damage": 0, "bonus_str": 0, "bonus_hp": 0, "armor": 0, "price": 3, "min_level": 1, "heal_percent": 30, "removes_trauma": False},
    {"name": "Эликсир Жизни", "slot": "potion", "class_type": "all", "min_damage": 0, "max_damage": 0, "bonus_str": 0, "bonus_hp": 0, "armor": 0, "price": 10, "min_level": 1, "heal_percent": 100, "removes_trauma": True},
]


class Database:
    def __init__(self):
        self._pool: Optional[Pool] = None

    async def connect(self) -> None:
        db_url = os.getenv("DB_URL", "").strip()
        if not db_url:
            raise ValueError("Set DB_URL in .env (e.g. postgresql+asyncpg://admin:pass@localhost/dbname)")
        # asyncpg ожидает postgresql://, а не postgresql+asyncpg://
        dsn = db_url.replace("postgresql+asyncpg://", "postgresql://", 1)
        self._pool = await asyncpg.create_pool(
            dsn=dsn,
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
            # players (player_class: rogue, tank, warrior — выбор при 2+ уровне)
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS players (
                    id SERIAL PRIMARY KEY,
                    telegram_id BIGINT UNIQUE NOT NULL,
                    username TEXT,
                    player_class TEXT
                )
            """)
            try:
                await conn.execute("ALTER TABLE players ADD COLUMN IF NOT EXISTS player_class TEXT")
            except Exception:
                pass
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
            # items: slot = head|body|legs|weapon|potion, class_type = all|rogue|tank|warrior
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS items (
                    id SERIAL PRIMARY KEY,
                    name TEXT NOT NULL,
                    slot TEXT NOT NULL,
                    class_type TEXT NOT NULL DEFAULT 'all',
                    min_damage INTEGER NOT NULL DEFAULT 0,
                    max_damage INTEGER NOT NULL DEFAULT 0,
                    bonus_str INTEGER NOT NULL DEFAULT 0,
                    bonus_hp INTEGER NOT NULL DEFAULT 0,
                    armor INTEGER NOT NULL DEFAULT 0,
                    price INTEGER NOT NULL DEFAULT 0,
                    min_level INTEGER NOT NULL DEFAULT 1,
                    heal_percent INTEGER NOT NULL DEFAULT 0,
                    removes_trauma BOOLEAN NOT NULL DEFAULT FALSE
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
                    p1_bandage_uses INTEGER NOT NULL DEFAULT 0,
                    p2_bandage_uses INTEGER NOT NULL DEFAULT 0
                )
            """)
            try:
                await conn.execute("ALTER TABLE battles ADD COLUMN IF NOT EXISTS p1_msg_id INTEGER")
                await conn.execute("ALTER TABLE battles ADD COLUMN IF NOT EXISTS p2_msg_id INTEGER")
                await conn.execute("ALTER TABLE battles ADD COLUMN IF NOT EXISTS p1_bandage_uses INTEGER NOT NULL DEFAULT 0")
                await conn.execute("ALTER TABLE battles ADD COLUMN IF NOT EXISTS p2_bandage_uses INTEGER NOT NULL DEFAULT 0")
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
            # Shadow fights (PvE vs AI; bandage_uses — до 2 бинтов за бой)
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS shadow_fights (
                    id SERIAL PRIMARY KEY,
                    player_id INTEGER NOT NULL REFERENCES players(id) ON DELETE CASCADE,
                    shadow_hp INTEGER NOT NULL,
                    player_hp INTEGER NOT NULL,
                    round INTEGER NOT NULL DEFAULT 1,
                    is_finished BOOLEAN NOT NULL DEFAULT FALSE,
                    bandage_uses INTEGER NOT NULL DEFAULT 0
                )
            """)
            try:
                await conn.execute("ALTER TABLE shadow_fights ADD COLUMN IF NOT EXISTS bandage_uses INTEGER NOT NULL DEFAULT 0")
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
            # Админы, назначенные владельцем (владелец 306039666 — единственный в коде)
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS admin_users (
                    telegram_id BIGINT PRIMARY KEY
                )
            """)
            try:
                await conn.execute("ALTER TABLE battles ADD COLUMN IF NOT EXISTS stake INTEGER NOT NULL DEFAULT 0")
                await conn.execute("ALTER TABLE items ADD COLUMN IF NOT EXISTS armor INTEGER NOT NULL DEFAULT 0")
                await conn.execute("ALTER TABLE items ADD COLUMN IF NOT EXISTS min_level INTEGER NOT NULL DEFAULT 1")
                await conn.execute("ALTER TABLE items ADD COLUMN IF NOT EXISTS class_type TEXT NOT NULL DEFAULT 'all'")
                await conn.execute("ALTER TABLE items ADD COLUMN IF NOT EXISTS heal_percent INTEGER NOT NULL DEFAULT 0")
                await conn.execute("ALTER TABLE items ADD COLUMN IF NOT EXISTS removes_trauma BOOLEAN NOT NULL DEFAULT FALSE")
            except Exception:
                pass
        await self._init_system_balance()
        await self._migrate_slots_and_class()
        await self.add_initial_items()
        await self._migrate_prices()
        logger.info("Database init complete")

    async def _migrate_prices(self) -> None:
        """Привести цены к ребалансу: зелье 5 кр., снаряжение в 10 раз дешевле."""
        async with self.pool.acquire() as conn:
            await conn.execute("UPDATE items SET price = 5 WHERE slot = 'potion'")
            await conn.execute(
                "UPDATE items SET price = GREATEST(1, price / 10) WHERE slot IN ('weapon', 'head', 'body', 'legs', 'chest')"
            )

    async def _migrate_slots_and_class(self) -> None:
        """Миграция: chest -> body, установить class_type для старых предметов."""
        async with self.pool.acquire() as conn:
            await conn.execute("UPDATE items SET slot = 'body' WHERE slot = 'chest'")
            await conn.execute("UPDATE items SET class_type = 'all' WHERE class_type IS NULL OR class_type = ''")

    async def _init_system_balance(self) -> None:
        """Одна строка с total_commission = 0, если таблица пуста."""
        async with self.pool.acquire() as conn:
            n = await conn.fetchval("SELECT COUNT(*) FROM system_balance")
            if not n or n == 0:
                await conn.execute("INSERT INTO system_balance (total_commission) VALUES (0)")

    async def add_initial_items(self) -> None:
        """Матрица классов: оружие (rogue/tank/warrior) и броня (head/body/legs) по уровням 1–3, два зелья."""
        async with self.pool.acquire() as conn:
            n = await conn.fetchval("SELECT COUNT(*) FROM items")
            if n and n > 0:
                # Существующая БД: добавить только отсутствующие новые предметы
                for row in _INITIAL_ITEMS:
                    exists = await conn.fetchval(
                        "SELECT 1 FROM items WHERE name = $1 AND slot = $2 LIMIT 1",
                        row["name"], row["slot"],
                    )
                    if not exists:
                        await conn.execute(
                            """
                            INSERT INTO items (name, slot, class_type, min_damage, max_damage, bonus_str, bonus_hp, armor, price, min_level, heal_percent, removes_trauma)
                            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12)
                            """,
                            row["name"], row["slot"], row["class_type"], row["min_damage"], row["max_damage"],
                            row["bonus_str"], row["bonus_hp"], row["armor"], row["price"], row["min_level"],
                            row.get("heal_percent", 0), row.get("removes_trauma", False),
                        )
                logger.info("Initial items: missing rows added")
                return
            # Новая БД: вставить полный набор
            for row in _INITIAL_ITEMS:
                await conn.execute(
                    """
                    INSERT INTO items (name, slot, class_type, min_damage, max_damage, bonus_str, bonus_hp, armor, price, min_level, heal_percent, removes_trauma)
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12)
                    """,
                    row["name"], row["slot"], row["class_type"], row["min_damage"], row["max_damage"],
                    row["bonus_str"], row["bonus_hp"], row["armor"], row["price"], row["min_level"],
                    row.get("heal_percent", 0), row.get("removes_trauma", False),
                )
        logger.info("Initial items added")

    # ----- Player -----
    async def get_player_by_telegram_id(self, telegram_id: int) -> Optional[dict]:
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT id, telegram_id, username, player_class FROM players WHERE telegram_id = $1",
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

    async def set_player_class(self, player_id: int, class_type: str) -> bool:
        """Установить класс: rogue, tank, warrior. Возвращает True при успехе."""
        if class_type not in ("rogue", "tank", "warrior"):
            return False
        async with self.pool.acquire() as conn:
            await conn.execute(
                "UPDATE players SET player_class = $1 WHERE id = $2",
                class_type,
                player_id,
            )
        return True

    async def get_or_create_player(self, telegram_id: int, username: Optional[str]) -> dict:
        p = await self.get_player_by_telegram_id(telegram_id)
        if p:
            return p
        return await self.create_player(telegram_id, username)

    # ----- Combat stats -----
    async def get_combat_stats(self, player_id: int, for_arena: bool = False) -> dict:
        """for_arena=True: использует current_hp с восстановлением 1 HP/мин. Классовые бонусы: rogue/tank/warrior."""
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
            player_row = await conn.fetchrow("SELECT player_class FROM players WHERE id = $1", player_id)
            player_class = (player_row["player_class"] if player_row and player_row["player_class"] else None)
            rows = await conn.fetch(
                """
                SELECT i.slot, i.class_type, i.bonus_str, i.bonus_hp, i.armor, i.min_damage, i.max_damage
                FROM inventory inv
                JOIN items i ON i.id = inv.item_id
                WHERE inv.player_id = $1 AND inv.is_equipped = TRUE
                """,
                player_id,
            )
            bonus_str = sum(r["bonus_str"] for r in rows)
            bonus_hp = sum(r.get("bonus_hp", 0) for r in rows)
            armor = sum(r.get("armor", 0) for r in rows if r.get("slot") in ("head", "body", "legs"))
            slots_equipped = {r["slot"] for r in rows}
            has_full_armor = {"head", "body", "legs"}.issubset(slots_equipped)
            weapon_min = 0
            weapon_max = 0
            weapon_class_type = None
            for r in rows:
                if r.get("slot") == "weapon" and (r["min_damage"] or r["max_damage"]):
                    weapon_min = r["min_damage"]
                    weapon_max = r["max_damage"]
                    weapon_class_type = r.get("class_type") or "all"
                    break
            strength = base["strength"] + bonus_str
            agility = base["agility"]
            intuition = base["intuition"]
            stamina = base["stamina"]
            level = base.get("level", 1)
            # Базовый MaxHP; Танк: +15 за выносливость вместо +5
            if player_class == "tank":
                max_hp = 30 + (level * 5) + (stamina * 15)
            else:
                max_hp = 30 + (level * 5) + (stamina * 5)
            # Классовые бонусы к броне и урону
            crit_bonus = 0.0
            block_bonus = 0.0
            if player_class == "rogue" and weapon_class_type == "rogue":
                crit_bonus = agility * 2.0
                weapon_min = weapon_min + agility
                weapon_max = weapon_max + agility
            elif player_class == "tank" and has_full_armor:
                armor = armor + stamina
            elif player_class == "warrior" and weapon_class_type == "warrior":
                weapon_min = weapon_min + strength * 2
                weapon_max = weapon_max + strength * 2
                block_bonus = float(strength)
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
                "player_class": player_class,
                "strength": strength,
                "agility": agility,
                "intuition": intuition,
                "stamina": stamina,
                "hp": hp_value,
                "max_hp": max_hp,
                "armor": armor,
                "weapon_min": weapon_min,
                "weapon_max": weapon_max if weapon_max else weapon_min,
                "crit_bonus": crit_bonus,
                "block_bonus": block_bonus,
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
    
    # ТОП ИГРОКОВ / ЛИДЕРБОРД
    async def get_leaderboard(self, limit: int = 100) -> list[dict]:
        """Список для рейтинга: player_id, name (username или Игрок), level, xp, class_name (Без класса если NULL)."""
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT p.id AS player_id,
                       COALESCE(p.username, 'Игрок') AS name,
                       s.level,
                       s.experience AS xp,
                       p.player_class
                FROM player_stats s
                JOIN players p ON p.id = s.player_id
                ORDER BY s.level DESC, s.experience DESC
                LIMIT $1
                """,
                limit,
            )
            out = []
            class_display = {"rogue": "Ловкач", "tank": "Танк", "warrior": "Мастер"}
            for r in rows:
                row = dict(r)
                row["class_name"] = class_display.get(row.get("player_class") or "", "Без класса")
                out.append(row)
            return out

    async def get_user_rank(self, player_id: int) -> int | None:
        """Позиция (#N) игрока в полном рейтинге (level DESC, xp DESC). None если игрок не найден."""
        async with self.pool.acquire() as conn:
            me = await conn.fetchrow(
                "SELECT level, experience FROM player_stats WHERE player_id = $1",
                player_id,
            )
            if not me:
                return None
            rank = await conn.fetchval(
                """
                SELECT COUNT(*) + 1
                FROM player_stats s
                JOIN players p ON p.id = s.player_id
                WHERE (s.level > $1 OR (s.level = $1 AND s.experience > $2))
                """,
                me["level"],
                me["experience"],
            )
            return rank

    # ----- Items & inventory -----
    async def get_player_inventory(self, player_id: int) -> list[dict]:
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT inv.id, inv.item_id, inv.is_equipped, i.name, i.slot, COALESCE(i.class_type, 'all') AS class_type, i.min_damage, i.max_damage, i.bonus_str, i.bonus_hp, COALESCE(i.armor, 0) AS armor, i.price, COALESCE(i.min_level, 1) AS min_level
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

    async def set_equipped(self, inv_id: int, player_id: int, equip: bool) -> tuple[bool, str]:
        """Установить экипировку. При equip=True проверяется min_level и class_type. Возвращает (успех, сообщение)."""
        _class_labels = {"rogue": "Ловкач", "tank": "Танк", "warrior": "Мастер"}
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT inv.id, inv.item_id, i.slot, COALESCE(i.min_level, 1) AS min_level, COALESCE(i.class_type, 'all') AS class_type FROM inventory inv JOIN items i ON i.id = inv.item_id WHERE inv.id = $1 AND inv.player_id = $2",
                inv_id,
                player_id,
            )
            if not row:
                return False, "Не найдено в инвентаре."
            if equip:
                pl = await conn.fetchrow("SELECT level FROM player_stats WHERE player_id = $1", player_id)
                player_level = pl["level"] if pl else 1
                min_level = row["min_level"] or 1
                if player_level < min_level:
                    return False, f"🛑 Ваш уровень слишком мал! Этот предмет доступен только с {min_level} уровня."
                item_class = (row["class_type"] or "all").lower()
                if item_class != "all":
                    pclass = await conn.fetchrow("SELECT player_class FROM players WHERE id = $1", player_id)
                    player_class = (pclass["player_class"] if pclass and pclass["player_class"] else None)
                    if player_class != item_class:
                        label = _class_labels.get(item_class, item_class)
                        return False, f"❌ Этот предмет предназначен только для класса: {label}."
                slot = row["slot"]
                await conn.execute(
                    "UPDATE inventory SET is_equipped = FALSE WHERE player_id = $1 AND item_id IN (SELECT id FROM items WHERE slot = $2)",
                    player_id, slot,
                )
            await conn.execute(
                "UPDATE inventory SET is_equipped = $1 WHERE id = $2 AND player_id = $3",
                equip, inv_id, player_id,
            )
            return True, "Надето" if equip else "Снято"

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
                SELECT pp.item_id, pp.quantity, i.name, COALESCE(i.heal_percent, 0) AS heal_percent, COALESCE(i.removes_trauma, FALSE) AS removes_trauma
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
        """Использовать зелье: −1 шт., восстановление по heal_percent, снять травму если removes_trauma. Возвращает (ok, msg)."""
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT quantity FROM player_potions WHERE player_id = $1 AND item_id = $2",
                player_id, item_id,
            )
            if not row or row["quantity"] < 1:
                return False, "Нет такого зелья."
            item = await conn.fetchrow("SELECT heal_percent, removes_trauma, name FROM items WHERE id = $1 AND slot = 'potion'", item_id)
            if not item:
                return False, "Предмет не является зельем."
            await conn.execute(
                "UPDATE player_potions SET quantity = quantity - 1 WHERE player_id = $1 AND item_id = $2",
                player_id, item_id,
            )
        heal_pct = item.get("heal_percent") or 100
        removes_trauma = item.get("removes_trauma") or False
        if heal_pct >= 100 and removes_trauma:
            await self.restore_player_hp_full(player_id)
            await self.clear_trauma(player_id)
            return True, "Вы выпили зелье! ❤️ Здоровье восстановлено до 100%, травма снята."
        import math
        stats = await self.get_combat_stats(player_id)
        max_hp = stats.get("max_hp", 40)
        heal_amount = max(1, math.ceil(max_hp * heal_pct / 100))
        async with self.pool.acquire() as conn:
            base = await conn.fetchrow("SELECT current_hp, hp_updated_at FROM player_stats WHERE player_id = $1", player_id)
            current = base["current_hp"] if base and base["current_hp"] is not None else max_hp
            new_hp = min(max_hp, current + heal_amount)
            await conn.execute(
                "UPDATE player_stats SET current_hp = $1, hp_updated_at = NOW() WHERE player_id = $2",
                new_hp, player_id,
            )
        if removes_trauma:
            await self.clear_trauma(player_id)
        return True, f"Использовано: {item['name']}. +{heal_amount} HP ({heal_pct}% от макс.)."

    async def get_potion_item_id(self, name: Optional[str] = None) -> Optional[int]:
        """ID зелья. По умолчанию — «Бинты» (30% хил в бою). name='Эликсир Жизни' для супер-хила."""
        async with self.pool.acquire() as conn:
            if name:
                row = await conn.fetchrow("SELECT id FROM items WHERE slot = 'potion' AND name = $1 LIMIT 1", name)
            else:
                row = await conn.fetchrow("SELECT id FROM items WHERE slot = 'potion' ORDER BY heal_percent ASC LIMIT 1")
            return row["id"] if row else None

    # ----- Shop -----
    async def buy_item(self, player_id: int, item_id: int) -> tuple[bool, str]:
        async with self.pool.acquire() as conn:
            item = await conn.fetchrow("SELECT * FROM items WHERE id = $1", item_id)
            if not item:
                return False, "Предмет не найден."
            stats = await conn.fetchrow("SELECT credits, level FROM player_stats WHERE player_id = $1", player_id)
            if not stats:
                return False, "Ошибка загрузки статов."
            item_class = (item.get("class_type") or "all").lower()
            if item_class != "all":
                pl = await conn.fetchrow("SELECT player_class FROM players WHERE id = $1", player_id)
                player_class = (pl["player_class"] if pl and pl["player_class"] else None)
                if player_class != item_class:
                    _labels = {"rogue": "Ловкач", "tank": "Танк", "warrior": "Мастер"}
                    label = _labels.get(item_class, item_class)
                    return False, f"❌ Этот предмет предназначен только для класса: {label}."
            min_level = item.get("min_level", 1) or 1
            if stats["level"] < min_level:
                return False, f"🛑 Ваш уровень слишком мал! Этот предмет доступен только с {min_level} уровня."
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
            if item["slot"] == "potion":
                return True, f"Куплено: {item['name']}. Используйте в Инвентаре."
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

    async def get_all_items_dict(self) -> list[dict]:
        """Список всех предметов (id, name, type/slot) для админки."""
        async with self.pool.acquire() as conn:
            rows = await conn.fetch("SELECT id, name, slot FROM items ORDER BY id")
            return [{"id": r["id"], "name": r["name"], "type": r["slot"]} for r in rows]

    async def admin_add_money(self, user_id: int, amount: int) -> bool:
        """Добавляет сумму к балансу игрока по Telegram ID. user_id = telegram_id."""
        player = await self.get_player_by_telegram_id(user_id)
        if not player:
            return False
        await self.add_credits(player["id"], amount)
        return True

    async def admin_add_item(self, user_id: int, item_id: int) -> bool:
        """Добавляет предмет игроку по Telegram ID. Зелья — в player_potions, остальное — в inventory."""
        player = await self.get_player_by_telegram_id(user_id)
        if not player:
            return False
        item = await self.get_item_by_id(item_id)
        if not item:
            return False
        pid = player["id"]
        if item.get("slot") == "potion":
            await self.add_potion(pid, item_id, 1)
        else:
            await self.add_item_to_inventory(pid, item_id, is_equipped=False)
        return True

    async def create_custom_item(
        self, name: str, item_type: str, stat: int, price: int = 0
    ) -> Optional[int]:
        """
        Создать уникальный предмет. type='weapon' -> damage=stat (min/max);
        type='armor' -> armor=stat, slot=body. Возвращает item_id или None.
        """
        slot = "weapon" if item_type == "weapon" else "body"
        min_dmg = max_dmg = stat if item_type == "weapon" else 0
        armor_val = stat if item_type == "armor" else 0
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                INSERT INTO items (name, slot, class_type, min_damage, max_damage, bonus_str, bonus_hp, armor, price, min_level, heal_percent, removes_trauma)
                VALUES ($1, $2, 'all', $3, $4, 0, 0, $5, $6, 1, 0, FALSE)
                RETURNING id
                """,
                name, slot, min_dmg, max_dmg, armor_val, price,
            )
            return row["id"] if row else None

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

    async def get_all_players_with_level(self) -> list[dict]:
        """Список всех игроков: telegram_id, username, level для /admin_users."""
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT p.telegram_id, p.username, s.level
                FROM players p
                JOIN player_stats s ON p.id = s.player_id
                ORDER BY s.level DESC, p.telegram_id
                """
            )
            return [dict(r) for r in rows]

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

    # ----- Admin users (назначенные владельцем) -----
    async def is_admin(self, telegram_id: int) -> bool:
        """True если пользователь в таблице admin_users (права выданы владельцем)."""
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT 1 FROM admin_users WHERE telegram_id = $1",
                telegram_id,
            )
            return row is not None

    async def add_admin(self, telegram_id: int) -> bool:
        """Добавить админа по Telegram ID. Возвращает True если добавлен."""
        try:
            async with self.pool.acquire() as conn:
                await conn.execute(
                    "INSERT INTO admin_users (telegram_id) VALUES ($1) ON CONFLICT (telegram_id) DO NOTHING",
                    telegram_id,
                )
            return True
        except Exception:
            return False

    async def remove_admin(self, telegram_id: int) -> bool:
        """Убрать права админа по Telegram ID."""
        async with self.pool.acquire() as conn:
            r = await conn.execute(
                "DELETE FROM admin_users WHERE telegram_id = $1",
                telegram_id,
            )
            return r == "DELETE 1"

    async def get_admin_ids(self) -> list[int]:
        """Список Telegram ID всех назначенных админов."""
        async with self.pool.acquire() as conn:
            rows = await conn.fetch("SELECT telegram_id FROM admin_users ORDER BY telegram_id")
            return [r["telegram_id"] for r in rows]

    # ----- Shadow fight (PvE vs AI) -----
    async def get_shadow_fight(self, fight_id: int) -> Optional[dict]:
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT id, player_id, shadow_hp, player_hp, round, is_finished, COALESCE(bandage_uses, 0) AS bandage_uses FROM shadow_fights WHERE id = $1",
                fight_id,
            )
            return dict(row) if row else None

    async def get_active_shadow_fight(self, player_id: int) -> Optional[dict]:
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT id, player_id, shadow_hp, player_hp, round, is_finished, COALESCE(bandage_uses, 0) AS bandage_uses
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
        """Тень подстраивается под уровень игрока: HP и урон равны или чуть ниже игрока."""
        stats = await self.get_combat_stats(player_id)
        if not stats:
            return None
        player_hp = stats["hp"]
        max_hp = stats.get("max_hp", 40)
        shadow_hp = max(1, int(max_hp * 0.9))  # Тень чуть слабее по HP
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                INSERT INTO shadow_fights (player_id, shadow_hp, player_hp, round, is_finished, bandage_uses)
                VALUES ($1, $2, $3, 1, FALSE, 0)
                RETURNING id, player_id, shadow_hp, player_hp, round, is_finished, bandage_uses
                """,
                player_id, shadow_hp, player_hp,
            )
            return dict(row) if row else None

    async def use_potion_shadow(self, fight_id: int, player_id: int) -> tuple[bool, int, str]:
        """Free Action: только Бинты, до 2 раз за бой. 30% HP, не тратит ход."""
        BANDAGE_LIMIT = 2
        fight = await self.get_shadow_fight(fight_id)
        if not fight or fight["is_finished"]:
            return False, 0, "Бой завершён."
        bandage_uses = fight.get("bandage_uses", 0) or 0
        if bandage_uses >= BANDAGE_LIMIT:
            return False, 0, f"Достигнут лимит использования бинтов за бой ({BANDAGE_LIMIT})."
        potion_id = await self.get_potion_item_id()
        if not potion_id or await self.get_potion_count(player_id, potion_id) < 1:
            return False, 0, "❌ У вас нет зелий! Купите их в магазине."
        stats = await self.get_combat_stats(player_id)
        max_hp = stats.get("max_hp", 40)
        import math
        async with self.pool.acquire() as conn:
            item = await conn.fetchrow("SELECT heal_percent FROM items WHERE id = $1", potion_id)
            heal_pct = item["heal_percent"] if item else 30
            heal = max(1, math.ceil(max_hp * heal_pct / 100))
            current_hp = fight["player_hp"]
            new_hp = min(max_hp, current_hp + heal)
            await conn.execute(
                "UPDATE player_potions SET quantity = quantity - 1 WHERE player_id = $1 AND item_id = $2 AND quantity >= 1",
                player_id, potion_id,
            )
            await conn.execute(
                "UPDATE shadow_fights SET player_hp = $1, bandage_uses = bandage_uses + 1 WHERE id = $2",
                new_hp, fight_id,
            )
        return True, new_hp, f"Бинты использованы. +{heal} HP ({heal_pct}% от макс.)."

    async def process_shadow_turn(
        self, fight_id: int, player_atk: int, player_blk: int
    ) -> tuple[Optional[dict], Optional[dict], list[str], bool, bool, int, int]:
        """
        ИИ Тени выбирает рандомные зоны. Возвращает (updated, stats, log_lines, player_won, leveled_up, gold_given, xp_given).
        """
        import random
        fight = await self.get_shadow_fight(fight_id)
        if not fight or fight["is_finished"]:
            return None, None, [], False, False, 0, 0
        player_id = fight["player_id"]
        stats = await self.get_combat_stats(player_id)
        if not stats:
            return None, None, [], False, False, 0, 0

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
            "crit_bonus": stats.get("crit_bonus", 0),
            "block_bonus": stats.get("block_bonus", 0),
        }
        # Тень подстраивается под игрока: урон чуть ниже (90%), без классовых бонусов
        shadow_wmin = max(1, int(wmin * 0.9))
        shadow_wmax = max(1, int(wmax * 0.9))
        shadow_combat: CombatStats = {
            "strength": stats["strength"],
            "agility": stats["agility"],
            "intuition": stats["intuition"],
            "stamina": stats["stamina"],
            "hp": fight["shadow_hp"],
            "max_hp": max_hp,
            "weapon_min": shadow_wmin,
            "weapon_max": shadow_wmax,
            "armor": arm,
            "level": lvl,
            "crit_bonus": 0,
            "block_bonus": 0,
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
        old_level = max(1, stats.get("level", 1))
        # Награды: базовая 3–7 кр. × уровень; итоговая = базовая × уровень. Поражение: 50% XP, 30% золота
        import random
        base_gold = random.randint(3, 7)
        gold_win = base_gold * old_level
        xp_win = 5 * old_level  # опыт по уровню
        gold_given, xp_given = 0, 0
        if player_won:
            gold_given, xp_given = gold_win, xp_win
            await self.add_credits(player_id, gold_win)
            await self.add_experience(player_id, xp_win)
        else:
            if is_finished:
                gold_given = max(1, int(gold_win * 0.3))
                xp_given = max(1, int(xp_win * 0.5))
                await self.add_credits(player_id, gold_given)
                await self.add_experience(player_id, xp_given)
        if is_finished:
            await self.restore_player_hp_full(player_id)
        new_stats = await self.get_combat_stats(player_id)
        leveled_up = (new_stats.get("level", 1) or 1) > old_level
        return updated, stats, log_lines, player_won, leveled_up, gold_given, xp_given

    async def finish_shadow_fight(self, fight_id: int) -> None:
        async with self.pool.acquire() as conn:
            await conn.execute("UPDATE shadow_fights SET is_finished = TRUE WHERE id = $1", fight_id)

    # ----- PvP Arena -----
    async def arena_join_queue(self, player_id: int, stake: int = 10) -> tuple[str, Optional[int], str]:
        """Ставка 10 кр. Matchmaking: противник того же уровня (±1)."""
        stats = await self.get_combat_stats(player_id)
        if not stats or stats.get("credits", 0) < stake:
            return "no_credits", None, "Недостаточно кредитов для ставки (нужно {} кр.).".format(stake)
        my_level = stats.get("level", 1)
        async with self.pool.acquire() as conn:
            existing = await conn.fetchval("SELECT 1 FROM arena_queue WHERE player_id = $1", player_id)
            if existing:
                return "waiting", None, "Вы уже в очереди."
            others = await conn.fetch("SELECT player_id FROM arena_queue WHERE player_id != $1", player_id)
            other_id = None
            for row in others:
                oid = row["player_id"]
                other_stats = await self.get_combat_stats(oid)
                if not other_stats or other_stats.get("credits", 0) < stake:
                    await conn.execute("DELETE FROM arena_queue WHERE player_id = $1", oid)
                    continue
                olvl = other_stats.get("level", 1)
                if abs(my_level - olvl) <= 1:
                    other_id = oid
                    break
            if not other_id:
                await conn.execute(
                    "UPDATE player_stats SET credits = credits - $1 WHERE player_id = $2",
                    stake, player_id,
                )
                await conn.execute(
                    "INSERT INTO arena_queue (player_id) VALUES ($1) ON CONFLICT (player_id) DO NOTHING",
                    player_id,
                )
                return "waiting", None, "Поиск соперника..."
            other_stats = await self.get_combat_stats(other_id)
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

    async def arena_leave_queue(self, player_id: int, stake: int = 10) -> tuple[bool, str]:
        """Удалить из очереди и вернуть ставку на баланс. Возвращает (успех, сообщение)."""
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow("SELECT 1 FROM arena_queue WHERE player_id = $1", player_id)
            if not row:
                return False, "Вы не в очереди."
            await conn.execute("DELETE FROM arena_queue WHERE player_id = $1", player_id)
        await self.add_credits(player_id, stake)
        return True, f"Поиск отменён. 💰 {stake} кр. возвращены на ваш баланс."

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
        """Free Action: только Бинты, до 2 раз за бой. 30% HP, не тратит ход."""
        BANDAGE_LIMIT = 2
        battle = await self.get_battle(battle_id)
        if not battle or battle["is_finished"]:
            return False, "Бой завершён."
        is_p1 = battle["player1_id"] == player_id
        col_hp = "player1_hp" if is_p1 else "player2_hp"
        col_bandage = "p1_bandage_uses" if is_p1 else "p2_bandage_uses"
        bandage_uses = battle.get(col_bandage, 0) or 0
        if bandage_uses >= BANDAGE_LIMIT:
            return False, f"Достигнут лимит использования бинтов за бой ({BANDAGE_LIMIT})."
        potion_id = await self.get_potion_item_id()
        if not potion_id or await self.get_potion_count(player_id, potion_id) < 1:
            return False, "❌ У вас нет зелий! Купите их в магазине."
        stats = await self.get_combat_stats(battle["player1_id"] if is_p1 else battle["player2_id"])
        max_hp = stats.get("max_hp", 40)
        import math
        async with self.pool.acquire() as conn:
            item = await conn.fetchrow("SELECT heal_percent FROM items WHERE id = $1", potion_id)
            heal_pct = item["heal_percent"] if item else 30
            heal = max(1, math.ceil(max_hp * heal_pct / 100))
            current_hp = battle[col_hp]
            new_hp = min(max_hp, current_hp + heal)
            await conn.execute(
                "UPDATE player_potions SET quantity = quantity - 1 WHERE player_id = $1 AND item_id = $2 AND quantity >= 1",
                player_id, potion_id,
            )
            await conn.execute(
                f"UPDATE battles SET {col_hp} = $1, {col_bandage} = COALESCE({col_bandage}, 0) + 1 WHERE id = $2",
                new_hp, battle_id,
            )
        return True, f"Бинты использованы. +{heal} HP ({heal_pct}% от макс.). Выберите атаку и защиту."

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

    async def close_stale_battles(self, minutes: int = 30, queue_stake: int = 10) -> None:
        """Завершает зависшие бои и удаляет из очереди с возвратом ставки."""
        interval = f"'{minutes} minutes'"
        async with self.pool.acquire() as conn:
            await conn.execute(f"UPDATE battles SET is_finished = TRUE WHERE is_finished = FALSE AND created_at < NOW() - INTERVAL {interval}")
            rows = await conn.fetch(
                f"SELECT player_id FROM arena_queue WHERE joined_at < NOW() - INTERVAL {interval}"
            )
            for row in rows:
                await self.add_credits(row["player_id"], queue_stake)
            await conn.execute(f"DELETE FROM arena_queue WHERE joined_at < NOW() - INTERVAL {interval}")

db = Database()