# Combats — текстовая MMORPG в Telegram

Бот на Python 3.11+, Aiogram 3, PostgreSQL (asyncpg).

## Установка

1. Клонируйте/скопируйте проект.
2. Создайте виртуальное окружение и установите зависимости:

```bash
python -m venv venv
venv\Scripts\activate   # Windows
pip install -r requirements.txt
```

3. Создайте БД PostgreSQL и заполните `.env`:

```env
BOT_TOKEN=ваш_токен_от_BotFather
DB_HOST=localhost
DB_PORT=5432
DB_NAME=combats_db
DB_USER=пользователь
DB_PASS=пароль
```

4. Запуск:

```bash
python main.py
```

Таблицы создаются при первом запуске автоматически.

## Команды и меню

- `/start` — регистрация, главное меню
- `/profile` или кнопка «Профиль» — статы, прокачка за свободные очки
- `/battle` или «Бой (манекен)» — PvE: удар по манекену, XP, 1–3 кр., 20% шанс дропа «Ржавый нож»
- `/inv` или «Инвентарь» — список вещей, Надеть/Снять
- `/shop` или «Магазин» — покупка за кредиты, продажа за 50% цены
- `/arena` или «Арена (PvP)» — поиск соперника, пошаговый бой (зоны удара/блока)

## Структура

- `main.py` — точка входа, роутеры
- `database/db.py` — подключение, таблицы, все SQL-операции
- `services/game_math.py` — формулы боя (HP, урон, уворот, крит, блок по зоне)
- `handlers/` — start, profile, battle, arena, inventory, shop
- `keyboards.py` — клавиатуры
