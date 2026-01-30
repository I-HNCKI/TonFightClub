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
- `/profile` или «Профиль» — статы, прокачка за свободные очки
- `/shadow` или «Бой с тенью» — PvE против ИИ (статы тени = ваши, HP тени 20), победа: +20 кр., +50 опыта
- `/inv` или «Инвентарь» — список вещей, Надеть/Снять
- `/shop` или «Магазин» — покупка за кредиты, продажа за 50% цены
- `/arena` или «Арена (PvP)» — ставка 100 кр., пошаговый бой; сдача = поражение, 90% банка победителю, 10% комиссия

## Структура

- `main.py` — точка входа, роутеры
- `database/db.py` — таблицы shadow_fights, system_balance, battles.stake, все SQL-операции
- `services/game_math.py` — формулы боя (HP, урон, уворот, крит, блок по зоне)
- `handlers/` — start, profile, shadow_fight, arena, inventory, shop, admin
- `keyboards.py` — клавиатуры
