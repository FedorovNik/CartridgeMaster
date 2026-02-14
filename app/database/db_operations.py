import aiosqlite
from typing import Optional, Tuple, Union
from datetime import datetime
import logging

DB_PATH = "database.db"
logger = logging.getLogger(__name__)

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

# Обновляет количество картриджа с штрихкодом `barcode` на `change`.
# Если barcode найден — возвращает кортеж (new_qty, name).
# Если barcode не найден — возвращает строку NOT_FOUND:barcode_or_name"
async def update_cartridge(barcode: str, change: int) -> tuple[int, str] | str:
    async with aiosqlite.connect(DB_PATH) as db:
        # Ищем картридж в cartridges, связанный с этим штрихкодом из таблицы barcodes
        sql_select = """
            SELECT c.id, c.cartridge_name, c.quantity 
            FROM cartridges c
            JOIN barcodes b ON c.id = b.cartridge_id
            WHERE b.barcode = ?
        """
        async with db.execute(sql_select, (barcode,)) as cursor:
            row = await cursor.fetchone()

        # Если не ничего не нашли, выходим с сигналом NOT_FOUND
        if not row:
            return f"NOT_FOUND:{barcode}"

        # После выполнения запроса заносим данные из кортежа в переменные и вычисляем новое количество
        c_id, name, current_qty = row
        new_qty = current_qty + change
        # Проверка на отрицательный остаток
        # Если после предыдущего вычисления вышло меньше нуля, выходим с сигналом NO_STOCK
        if new_qty < 0:
            return f"NO_STOCK:{name}"

        # Берем текущее время для записи для обновления записей в таблицах
        # Встроенный current_timestamp sqlite дает не то время, лень разбираться.
        # Разница в пару милисекунд несущественна, так что просто генерируем время на стороне питона.
        current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        # Обновляем количество и время последнего обновления в основной таблице
        await db.execute(
            "UPDATE cartridges SET quantity = ?, last_update = ? WHERE id = ?",
            (new_qty, current_time, c_id)
        )

        # Логируем историю об операции в таблицу (action_type: 1 если приход/ноль, 0 если расход)
        action_type = 1 if change >= 0 else 0
        current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        await db.execute("""
            INSERT INTO update_history (barcode, action_type, update_quantity, balance, update_time)
            VALUES (?, ?, ?, ?, ?)
        """, (barcode, action_type, abs(change), new_qty, current_time)
        )
        await db.commit()
        return new_qty, name

# Выборка по всем картриджам из всех базы,
# Вовзращает кортеж (id, cartridge_name, quantity, all_barcodes, last_update) по каждому айдишнику.
async def get_all_cartridges():
    async with aiosqlite.connect(DB_PATH) as db:
        sql_select ="""
            SELECT c.id, c.cartridge_name, c.quantity, group_concat(b.barcode, '; ') as all_barcodes, c.last_update
            FROM barcodes b LEFT JOIN cartridges as c ON c.id == b.cartridge_id
            GROUP by b.cartridge_id
        """
        async with db.execute(sql_select, ()) as cursor:
            return await cursor.fetchall()
        
# Обновляет параметр notice_enabled в базе пользователей, для включения/отключения уведомлений.
async def update_user_notice(telegram_id: int, notice_enabled: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
                    "UPDATE users SET notice_enabled = ? WHERE telegram_id = ?",(notice_enabled, telegram_id)
                )
        await db.commit()