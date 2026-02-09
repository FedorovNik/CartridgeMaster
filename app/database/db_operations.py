import aiosqlite
from typing import Optional, Tuple, Union
from datetime import datetime

DB_PATH = "database.db"


async def create_tables():
    async with aiosqlite.connect(DB_PATH) as db:
        # Таблица пользователей, в которой хранятся TG-ID, имя и статус уведомлений
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                telegram_id INTEGER UNIQUE,
                first_name TEXT,
                notice_enabled BOOLEAN DEFAULT 0
            )
        """)
        # Таблица картриджей, у каждой модели уникальный ID, количество и время последнего обновления
        await db.execute("""
            CREATE TABLE IF NOT EXISTS cartridges (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                cartridge_name TEXT,
                quantity INTEGER,
                last_update DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        # Таблица для связи штрихкода и картриджа, так как у взаимозаменяемых катриджей могут быть разные баркоды.
        # Нет смысла хранить их в разных строках, так как по факту это один и тот же картридж. 
        await db.execute("""
            CREATE TABLE IF NOT EXISTS barcodes (
                barcode TEXT PRIMARY KEY,
                cartridge_id INTEGER,
                FOREIGN KEY (cartridge_id) REFERENCES cartridges (id)
            )
        """)
        # Таблица истории изменений количества картриджей, для будущих прогнозов и аналитики.
        await db.execute("""
            CREATE TABLE IF NOT EXISTS update_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                barcode TEXT,
                action_type BOOLEAN,
                update_quantity INTEGER,
                balance INTEGER,
                update_time DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        await db.commit()

# Добавляет пользователя в базу по ID и имени
async def add_user(telegram_id: int, first_name: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT OR IGNORE INTO users (telegram_id, first_name)
            VALUES (?, ?)
        """, (telegram_id, first_name))
        await db.commit()

# Дропает пользователя из базы, возращает целое число о количестве выполненных операций.
# Если есть два пользователя с одинаковым ID дропнет обоих 
async def del_user(telegram_id: int) -> bool:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("DELETE FROM users WHERE telegram_id = ?", (telegram_id,))
        await db.commit()
        # Если удалено больше 0 строк, значит пользователь был в базе
        return cursor.rowcount > 0

# Вовзращает всю инфу по всем пользователям
async def get_all_users():
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT * FROM users") as cursor:
            return await cursor.fetchall()
        
# Вовзращает выборку из всех айдишников пользователей базы у которых включены уведомления)
async def get_tg_id_list_notification():
    async with aiosqlite.connect(DB_PATH) as db:
        # Выполняем запрос на выборку всех ID
        async with db.execute("SELECT telegram_id FROM users WHERE notice_enabled = 1") as cursor:
            rows = await cursor.fetchall()
            
            # Извлекаем айдишник из кортежей (fetchall возвращает список кортежей вида [(123,), (456,)])
            return [row[0] for row in rows]
        
# Используется в связке с базовым фильтром, для обработки сообщений только "доверенных" лиц из базы
# Ищет пользователя по айдишнику, возвращает строку из таблицы.
async def user_exists(telegram_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT 1 FROM users WHERE telegram_id = ?", (telegram_id,)) as cursor:
            result = await cursor.fetchone()
            return result is not None
            # fetchone() передвигает указатель курсора при вызове!

# Обновляет количество картриджа с штрихкодом `model` на `change` (плюс/минус).
# Если картридж найден — возвращает кортеж (model, short_name, new_quantity).
# Если не найден — возвращает строку со спец сигналом и  переданным штрихкодом `model`.
async def update_cartridge(model: str, change: int) -> Union[Tuple[str, str, int], str]:

    async with aiosqlite.connect(DB_PATH) as db:
        # Проверяем, есть ли такой картридж
        async with db.execute("SELECT quantity, short_name FROM cartridges WHERE model = ?", (model,)) as cursor:
            row = await cursor.fetchone()
            if row:
                current_qty = row[0]
                short_name = row[1]
                # Если пытаются уменьшить, но уже 0 — не уменьшаем и возвращаем специальный код
                if change < 0 and current_qty <= 0:
                    # Специальный сигнал: недостаточно на складе
                    return f"NO_STOCK:{model}"

                new_qty = max(0, current_qty + change)

                # Берем текущее время для записи для обновления записей в таблицах
                current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

                # Обновление количества и временной метки в таблице картриджей
                await db.execute(
                    "UPDATE cartridges SET quantity = ?, last_updated = ? WHERE model = ?",
                    (new_qty, current_time, model),
                )

                # Обновление базы с логами для будущих прогнозов расходов. 
                # Попробуем скормить нейронке эти записи
                # Переменная action_type просто кратко хранит информацию 
                # о типе операции - приход или расход.
                # А обновляемое количество update_quantity хранится в базе по модулю  
                action_type: bool
                if change >= 0:
                    action_type = 1
                else:
                    action_type = 0
                await db.execute("""
                    INSERT OR IGNORE INTO cart_update_log (model, action_type, update_quantity, balance, last_updated ) VALUES (?, ?, ?, ?, ?)
                    """, 
                    (model, action_type, abs(change), new_qty, current_time )
                )
                await db.commit()
                return model, short_name, new_qty
            else:
                # Возвращаем строку со штрихкодом если не найден
                return f"NOT_FOUND:{model}"

# Просто выборка по всем картриджам из всех базы
async def get_all_cartridges():
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT model, short_name, quantity, last_updated FROM cartridges") as cursor:
            return await cursor.fetchall()
        
# Обновляет параметр notice_enabled в базе пользователей, для включения/отключения уведомлений.
async def update_user_notice(telegram_id: int, notice_enabled: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
                    "UPDATE users SET notice_enabled = ? WHERE telegram_id = ?",(notice_enabled, telegram_id)
                )
        await db.commit()

# Просто проверяет наличие в базе
#async def cartridge_exist(telegram_id: int) -> bool:
#    async with aiosqlite.connect(DB_PATH) as db:
#        async with db.execute("SELECT 1 FROM cartridges WHERE model = ?", (telegram_id,)) as cursor:
#            result = await cursor.fetchone()
#            return result is not None





