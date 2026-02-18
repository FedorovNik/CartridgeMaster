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
        # Добавление меня по умолчанию =)
        await db.execute("""
            INSERT OR IGNORE INTO users (telegram_id, first_name, notice_enabled)
            VALUES (?, ?, ?)
        """, (539356755, "Никита", True))

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
                index_number INTEGER PRIMARY KEY AUTOINCREMENT,
                barcode TEXT,
                action_type BOOLEAN,
                update_quantity INTEGER,
                balance INTEGER,
                update_time DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        await db.commit()

# Добавляет пользователя в базу по ID и имени
# Ничего не возвращает
async def add_user(telegram_id: int, first_name: str):
    async with aiosqlite.connect(DB_PATH) as db:
        sql_req_new_user="""
            INSERT OR IGNORE INTO users (telegram_id, first_name)
            VALUES (?, ?)
        """
        try:
            await db.execute(sql_req_new_user, (telegram_id, first_name))
        except Exception as e:
            logger.error('|  SQLITE  |    ИСКЛЮЧЕНИЕ   |  Таблица users           | Вызвано исключение при добавлении пользователя с telegram_id={telegram_id}!')
            return None
        logger.info(f'|  SQLITE  |     УСПЕШНО     |  Таблица users           | Добавление пользователя с telegram_id={telegram_id} выполнено!')

        await db.commit()

# Удаляет пользователя из базы, возращает целое число о количестве выполненных операций.
# Если есть два пользователя с одинаковым ID дропнет обоих
# Возвращает: целое число (количество удалений строк в базе)
#             0, если не найден
async def del_user(telegram_id: int) -> bool:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("DELETE FROM users WHERE telegram_id = ?", (telegram_id,))
        await db.commit()
        # Если удалено больше 0 строк, значит пользователь был в базе
        # Возвращаем количество удаленных строк
        return cursor.rowcount > 0

# Поиск инфы по всем пользователям базы
# Возвращает: список из кортежей (id, telegram_id, first_name, notice_enabled)
async def get_all_users():
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT * FROM users") as cursor:
            return await cursor.fetchall()

# Поиск всех пользователей, у которых включены уведомления
# Вовзращает список из ID пользователей базы, у которых включены уведомления
async def get_tg_id_list_notification():
    async with aiosqlite.connect(DB_PATH) as db:
        # Выполняем запрос на выборку всех ID
        async with db.execute("SELECT telegram_id FROM users WHERE notice_enabled = 1") as cursor:
            rows = await cursor.fetchall()
            # Извлекаем айдишник из кортежей (fetchall возвращает список кортежей вида [(123,), (456,)])
            return [row[0] for row in rows]
        
# Ищет пользователя по айдишнику в базе, используется в связке с базовым фильтром для обработки
# сообщений только "доверенных" лиц из базы.
# Возвращает: Кортеж из ID пользователя, если он найден
#             None
async def user_exists(telegram_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT 1 FROM users WHERE telegram_id = ?", (telegram_id,)) as cursor:
            # В результате строка из базы или None, если ничего не найдено
            result = await cursor.fetchone()
            # Возвращаем кортеж
            return result is not None

# Обновляет количество картриджа со штрихкодом `barcode` на `change`.
# Возвращает: кортеж (new_qty, name) если штрих не найден.
#             строку NOT_FOUND:barcode_or_name"
async def update_cartridge_count(barcode: str, change: int) -> tuple[int, str] | str:
    async with aiosqlite.connect(DB_PATH) as db:
        # Ищем картридж в cartridges, связанный с этим штрихкодом из таблицы barcodes
        sql_req_find_by_barcode = """
            SELECT c.id, c.cartridge_name, c.quantity 
            FROM cartridges c
            JOIN barcodes b ON c.id = b.cartridge_id
            WHERE b.barcode = ?
        """
        async with db.execute(sql_req_find_by_barcode, (barcode,)) as cursor:
            # Кортеж из базы в строку row, или None в row если ничего не найдено
            row = await cursor.fetchone()

        # Если не ничего не нашли, выходим с сигналом NOT_FOUND
        if not row:
            logger.warning(f"|  SQLITE  |    НЕ НАЙДЕНО   |  Таблица barcodes        | Штрих-код: {barcode} не найден в базе!")
            return f"NOT_FOUND:{barcode}"

        # После выполнения запроса заносим данные из кортежа в переменные и вычисляем новое количество
        c_id, name, current_qty = row
        new_qty = current_qty + change
        # Проверка на отрицательный остаток
        # Если после предыдущего вычисления вышло меньше нуля, выходим с сигналом NO_STOCK
        if new_qty < 0:
            logger.warning(f"|  SQLITE  |   НЕДОПУСТИМО   |  ПРОВЕРКА ВВОДА          | Картридж найден, но выбрано недопустимое изменение количества!")
            return f"NO_STOCK:{name}"

        # Берем текущее время для записи для обновления записей в таблицах
        # Встроенный current_timestamp sqlite дает не то время, лень разбираться.
        # Разница в пару милисекунд несущественна, так что просто генерируем время на стороне питона.
        current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        # Обновляем количество и время последнего обновления в основной таблице
        sql_req_update_cartridges = """
                UPDATE cartridges
                SET quantity = ?, last_update = ?
                WHERE id = ?
                """
        try:
            await db.execute(sql_req_update_cartridges, (new_qty, current_time, c_id) )
        except Exception as e:
            logger.error("|  SQLITE  |    ИСКЛЮЧЕНИЕ   |  Таблица cartridges      | Вызвано исключение при попытке обновления id={c_id}!")
            return None
        logger.info(f'|  SQLITE  |     УСПЕШНО     |  Таблица cartridges      | Обновление позиции с id={c_id} выполнено!')



        # Логируем историю об операции в таблицу (action_type: 1 если приход/ноль, 0 если расход)
        action_type = 1 if change >= 0 else 0
        current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        sql_req_new_history_string = """
                INSERT INTO update_history (barcode, action_type, update_quantity, balance, update_time)
                VALUES (?, ?, ?, ?, ?)
            """
        try:
            await db.execute(sql_req_new_history_string, (barcode, action_type, abs(change), new_qty, current_time) )
        except Exception as e:
            logger.error("|  SQLITE  |    ИСКЛЮЧЕНИЕ   |  Таблица update_history  | Вызвано исключение при попытке обновления id={c_id}!")
            return None
        logger.info(f'|  SQLITE  |     УСПЕШНО     |  Таблица update_history  | Обновление позиции с id={c_id} выполнено!')

        # Комитим базу и возвращаем кортеж из нового количества и имени картриджа
        await db.commit()
        return new_qty, name

# Выборка по всем картриджам из всех базы
# Возвращает: кортеж (id, cartridge_name, quantity, all_barcodes, last_update) по каждому айдишнику.
async def get_all_cartridges():
    async with aiosqlite.connect(DB_PATH) as db:
        sql_req ="""
            SELECT c.id, c.cartridge_name, c.quantity, group_concat(b.barcode, '; ') as all_barcodes, c.last_update
            FROM barcodes b LEFT JOIN cartridges as c ON c.id == b.cartridge_id
            GROUP by b.cartridge_id
        """
        async with db.execute(sql_req, ()) as cursor:
            # Возвращаем СПИСОК кортежей, по одному на каждый картридж
            return await cursor.fetchall()

# Поиск по имени
# Возвращает: кортеж (id, cartridge_name, all_barcodes, quantity, last_update) по ИМЕНИ картриджа
#             None, если не найдено
async def get_cartridge_by_name(cartridge_name: str):
    async with aiosqlite.connect(DB_PATH) as db:
        sql_req ="""
            SELECT c.id, c.cartridge_name,  group_concat(b.barcode, '; ') as all_barcodes, c.quantity, c.last_update
            FROM cartridges as c 
            JOIN barcodes as b ON c.id == b.cartridge_id
            WHERE c.cartridge_name LIKE ?
            GROUP BY c.id
        """
        async with db.execute(sql_req, (cartridge_name,)) as cursor:
            # Возвращаем кортеж из базы по нужной позиции или None, если ничего не найдено
            return await cursor.fetchone()
        
# Поиск по штрих-коду
# Используется подзапрос, т.к. сначала нужно найти ID картриджа и только потом выполнить JOIN по айдишнику
# GROUP BY c.id обязательно, иначе будет сыпаться исключения в блоке обработки результатов. 
# Если не нашлось ничего, то нужно вернуть None, а не кортеж из нонов..
# Возвращает: кортеж (id, cartridge_name, all_barcodes, quantity, last_update) по баркоду картриджа
#             None, если не найдено
async def get_cartridge_by_barcode(barcode: str):
    async with aiosqlite.connect(DB_PATH) as db:
        sql_req = """
            SELECT c.id, c.cartridge_name, group_concat(b.barcode, '; ') as all_barcodes, c.quantity, c.last_update
            FROM cartridges as c
            JOIN barcodes b ON c.id = b.cartridge_id
            WHERE c.id = ( SELECT cartridge_id FROM barcodes WHERE barcode = ? )
            GROUP BY c.id
        """
        async with db.execute(sql_req, (barcode,)) as cursor:
            # Возвращаем кортеж из базы по нужной позиции или None, если ничего не найдено
            return await cursor.fetchone()
        
# Обновляет параметр notice_enabled в базе пользователей, для включения/отключения уведомлений.
# Изменяет базу, ничего не возвращает
async def update_user_notice(telegram_id: int, notice_enabled: int):
    async with aiosqlite.connect(DB_PATH) as db:
        sql_req = """
            UPDATE users
            SET notice_enabled = ?
            WHERE telegram_id = ?
        """
        await db.execute(sql_req, (notice_enabled, telegram_id) )
        await db.commit()

# Создает новую строку в базе cartridges и barcodes по переданным параметрам.
# Изменяет базу, возвращает True или False
async def insert_new_cartridge(barcode: str, cartridge_name: str, quantity: int):
    async with aiosqlite.connect(DB_PATH) as db:
        current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')


        # Запрос на вставку нового картриджа в cartridges
        sql_req_new_cartridge = """
                INSERT INTO cartridges (cartridge_name, quantity, last_update)
                VALUES (?, ?, ?)
        """
        try:
            # Результат выполнения заносим в объект курсора, у него есть метод для получения ID последней записи
            curs_res = await db.execute(sql_req_new_cartridge, (cartridge_name, quantity, current_time) )
            new_cartridge_id = curs_res.lastrowid
        except Exception as e:
            logger.error("|  SQLITE  |    ИСКЛЮЧЕНИЕ   |  Таблица cartridges      | Вызвано исключение при попытке добавления нового картриджа!")
            return None
        logger.info(f'|  SQLITE  |     УСПЕШНО     |  Таблица cartridges      | Добавление позиции с id={new_cartridge_id} выполнено!')    


        # Запрос на вставку штрих кода и определенным ID картриджа в barcodes
        sql_req_new_barcode = """
                INSERT INTO barcodes (barcode, cartridge_id)
                VALUES (?, ?)
        """
        try:
            await db.execute(sql_req_new_barcode, (barcode, new_cartridge_id) )
        except Exception as e:
            logger.info(f'|  SQLITE  |    ИСКЛЮЧЕНИЕ   |  Таблица barcodes        | Вызвано исключение при попытке добавления нового картриджа!')
        logger.info(f'|  SQLITE  |     УСПЕШНО     |  Таблица barcodes        | Добавление позиции с id={new_cartridge_id} выполнено!')


        await db.commit()
        return True
        


# Поиск картриджа по id
# Возвращает: кортеж (id, cartridge_name, all_barcodes, quantity, last_update) по ID картриджа
#             None, если не найдено
async def get_cartridge_by_id(id: str):
    async with aiosqlite.connect(DB_PATH) as db:
        sql_req = """
                SELECT c.id, c.cartridge_name, group_concat(b.barcode, '; ') as all_barcodes, c.quantity, c.last_update
                FROM cartridges as c
                JOIN barcodes b ON c.id = b.cartridge_id
                WHERE c.id = ?
                GROUP BY c.id
        """
        async with db.execute(sql_req, (id,)) as cursor:
            # Возвращаем кортеж из базы по выбранному картриджу
            return await cursor.fetchone()

# Удаление картриджа из всех таблиц по уникальному ID
# Возdращает TRUE или FALSE, выполнились все операции или нет.
async def delete_cartridge(id: str):
    async with aiosqlite.connect(DB_PATH) as db:
        # Сначала удаляем из barcodes (т.к. есть связи с первой таблицей) и только потом из cartridges
        sql_req_barcodes = """
        DELETE FROM barcodes as b
        WHERE b.cartridge_id = ?
        """
        sql_req_cartridges = """
        DELETE FROM cartridges as c
        WHERE c.id = ?
        """
        # Удаление из barcodes
        try:
            # Норм поведение
            if await db.execute(sql_req_barcodes,   (id,) ):
                logger.info(f'|  SQLITE  |     УСПЕШНО     |  Таблица barcodes        | Позиции с id={id} удалены!')
            # Если косяк в sql запросе и переданном id
            else:
                logger.error(f'|  SQLITE  |     ОШИБКА      |  Таблица barcodes        | Позиции с id={id} не удалены!')
                return False
        # Еще обработка исключения на всякий случай
        except Exception as e:
            logger.info("|  SQLITE  |    ИСКЛЮЧЕНИЕ   |  Таблица barcodes        | Вызвано исключение при попытки удаления id={id}!")
            return False

        # Удаление из cartridges
        try:
            # Норм поведение
            if await db.execute(sql_req_cartridges,   (id,) ):
                logger.info(f'|  SQLITE  |     УСПЕШНО     |  Таблица cartridges      | Позиции с id={id} удалены!')
            # Если косяк в sql запросе и переданном id
            else:
                logger.error(f'|  SQLITE  |     ОШИБКА      |  Таблица cartridges      | Позиции с id={id} не удалены!')
                return False
        # Еще обработка исключения на всякий случай
        except Exception as e:
            logger.info("|  SQLITE  |    ИСКЛЮЧЕНИЕ   |  Таблица cartridges      | Вызвано исключение при попытке удаления id={id}!")
            return False

        await db.commit()
        return True
