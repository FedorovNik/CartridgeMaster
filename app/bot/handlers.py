
from sqlite3 import Row
from sqlite3 import Row
from sqlite3 import Row
from sqlite3 import Row
from aiogram import Bot, Router, F
from aiogram.filters import Command, BaseFilter, CommandObject
from aiogram.methods.send_message import SendMessage
from aiogram.types import Message



import platform
from importlib.metadata import version
from app.database.db_operations import add_user, get_all_users, user_exists, del_user,\
                                       get_all_cartridges, get_tg_id_list_notification,\
                                       get_cartridge_by_name, update_cartridge, update_user_notice,\
                                       get_cartridge_by_barcode
import logging

import socket
hostname: str = socket.gethostname()
local_ip: str = socket.gethostbyname(hostname)


logger: logging.Logger = logging.getLogger(__name__)

def is_number(s) -> bool:
    try:
        # Если преобразуется в float без ошибок, значит это число (может быть целым или с плавающей точкой)
        float(s) 
        return True
    except ValueError:
        return False

# Объект роутера класса Роутер 
rt = Router()

# Базовый фильтр для проверки авторизованного пользователя
class AuthorizedFilter(BaseFilter):
    async def __call__(self, message: Message) -> bool:
        # Вызываем метод базы и закидываем в него только ИД отправителя сообщения,
        # полученный из объекта message. Любой бред полученный от рандомов будет пропускаться
        # (защита от инъекций), но к сожалению всё равно будет дергаться база при
        # каждом сообщении, иначе хз как сделать. 
        return await user_exists(message.from_user.id)

# Применяем его ко всем сообщениям в роутере
rt.message.filter(AuthorizedFilter())

@rt.message(Command("start"))
async def start(message: Message) -> None:
    
    python_ver: str = platform.python_version()
    aiogram_ver: str = version("aiogram")
    aiohttp_ver: str = version("aiohttp")
    aiosqlite_ver: str = version("aiosqlite")
    await message.answer(f"<b>Привет, {message.from_user.first_name}!</b>\n"
                        f"Этот бот работает на асинхронном python фреймворке для ТГ-ботов <code>aiogram</code>.\n"
                        f"Вся БД SQLite хранится в файле <code>database.db</code>, коротый находится в той же директории с программой.\n"
                        f"Любое сообщение, отправленное боту проверяется - находится ли отправитель в базе (таблице users).\n"
                        f"Бот отвечает только людям, которые находятся в базе.\n\n"
                        f"Бот, локальный веб-сервер работают в 1 процессе и 1 потоке, с помощью кооперативной многозадачности, \
                            которую обеспечивает асинхронная библиотека <code>asyncio</code>.\n\n"
                        f"Программа логически разделена на 2 модуля (директории <b>bot</b> и <b>web</b>):\n"
                        f"1. Диспетчер бота регистрирует и обрабатывает все события, получаемые от серверов телеграма.\n"
                        f"2. HTTP-сервер принимает и обрабатывает POST-запросы от ТСД по адресу http://{local_ip}:8080/scan.\
                            Трафик между ТСД и веб-сервером передается в зашифрованном виде (алгоритм AES).\
                            \nКлюч шифрования AES_KEY зашит в коде на серверной части и ТСД-шнике.\n\n"
                        f"<b>Краткая информация о версиях:</b>\n"
                        f"Python:  <code>{python_ver}</code>.\n"
                        f"Aiogram: <code>{aiogram_ver}</code>\n"
                        f"Aiohttp: <code>{aiohttp_ver}</code>\n"
                        f"Aiosqlite: <code>{aiosqlite_ver}</code>\n\n"
                        f"Для получения справки по командам бота вызови <b>/help</b>\n"
                        ,parse_mode="HTML"
    )

@rt.message(Command("help"))
async def help(message: Message) -> None:
    await message.answer(
    f"<b>Работа с таблицей картриджей:\n</b>"
    f"<b>/list</b>\nВывести всю инфу по картриджам.\n"
    f"<b>/renew</b>\nОбновить количество определенного картриджа.\n"
    f"<b>/insert</b>\nДобавить новый картридж, отсутствующий в таблице.\n"
    f"<b>/delete</b>\nУдалить запись о картридже из таблицы.\n\n"

    f"<b>Работа с таблицей пользователей:\n</b>"
    f"<b>/users</b>\nВывести список всех пользователей.\n"
    f"<b>/adduser</b>\nДобавить нового пользователя в таблицу.\n"
    f"<b>/deluser</b>\nУдалить пользователя из таблицы.\n"
    f"<b>/notice</b>\nВключение/отключение уведомлений пользователям в личку от ТСД.\n"
    ,parse_mode="HTML"
    )

@rt.message(Command("adduser"))
async def adduser(message: Message, command: CommandObject) -> Message | None:
    # Проверяем, что аргументы вообще есть
    if not command.args:
        return await message.answer("Команда добавления пользователя требует аргументов.\n"
                                    "Пример синтаксиса:\n"
                                    "<b>/adduser TG_ID USER_NAME</b>\n",
                                    parse_mode="HTML")
    
    # Проверка кол-ва аргументов, ожидается только ID и NAME
    parts: list[str] = command.args.split(maxsplit=1)
    if len(parts) != 2:
        return await message.answer("Неверное количество аргументво команды!")
    user_id_str, user_name = parts

    # Проверка на число
    if not user_id_str.isdigit():
        return await message.answer("ID должен состоять только из цифр!")

    # Если все ок пишем в базу
    await add_user(
        telegram_id=int(user_id_str),
        first_name=user_name
    )
    
    await message.answer(f"Пользователь <b>{user_name}</b> с ID: <b>{user_id_str}</b> добавлен.", parse_mode="HTML")

@rt.message(Command("deluser"))
async def deluser(message: Message, command: CommandObject) -> Message | None:
    # Проверяем, что аргументы вообще есть
    if not command.args:
        return await message.answer("Команда удаления пользователя требует аргументов.\n"
                                    "Пример синтаксиса:\n"
                                    "<b>/deluser TG_ID</b>\n",
                                    parse_mode="HTML")
    
    # Проверка кол-ва аргументов, ожидается только один айдишник
    parts: list[str] = command.args.split(maxsplit=1)
    if len(parts) != 1:
        return await message.answer("Неверное количество аргументов команды!")
    # Единственный элемент списка заносим в переменную
    user_id_str: str = parts[0]

    # Проверка на число
    if not user_id_str.isdigit():
        return await message.answer("ID должен состоять только из цифр!")

    # Если все ок вызываем функцию базы, результат выполнения del_user сравниваем - удалился или нет
    result_del: bool = await del_user(telegram_id=int(user_id_str))
    if result_del > 0:
        await message.answer(f"Пользователь c ID: <b>{user_id_str}</b> удален.", parse_mode="HTML")
    else:
        await message.answer(f"Пользователя c ID: <b>{user_id_str}</b> нет в базе.", parse_mode="HTML")
    

@rt.message(Command("users"))
async def list_users(message: Message) -> None:
    users: logging.Iterable[Row] = await get_all_users()
    if not users:
        await message.answer("Список пользователей в базе пуст!")
        return

    text = "Список пользователей:\n\n"
    for user in users:
        text += f"Имя:  <b>{user[2]}</b>  -  ID: {user[1]} -  Уведомления: {user[3]}\n"
    await message.answer(text, parse_mode="HTML")

# Хэндлер для команды /list, выводит всю инфу по картриджам из базы.
@rt.message(Command("list"))
async def list_cartridges(message: Message) -> Message | SendMessage | None:
    # В cartridges копируем кортеж из (id, cartridge_name, quantity, all_barcodes, last_update) по каждому картриджу.
    cartridges: logging.Iterable[Row] = await get_all_cartridges()
    #logger.info(cartridges)
    # Простая проверка на существование 
    if not cartridges:
        return await message.answer("Склад пуст!\
                                    \nКартриджи не найдены.", parse_mode="HTML")

    header = "<b>Текущие остатки на складе:</b>\n"
    header += "<code>" + "—" * 33 + "</code>\n"
    
    text_lines = []
    # Нужно пройтись по каждому айтему из кортежа cartridges и собрать текст text_lines для ответа
    for item in cartridges:

        # элемент кортежа cartridges распаковываем в переменные для удобства
        id, cartridge_name, quantity, all_barcodes, last_update = item

        # Индикатор остатка, можно потом создать в базе поле с минимальными порогами для каждого картриджа и сравнивать с ним.
        status_color: str = ""
        if quantity >= 6:
            status_color = "✅ Норм!  "
        elif quantity >= 3:
            status_color = "⚠️Средне!"
        elif quantity >= 0:
            status_color = "❌ Мало!  "
        else:
            # Если количество отрицательное, то это косяк в базе, который нужно исправить
            logger.error(f"| TELEGRAM | /list | Отрицательное количество по позиции | ID: {id} Наименование: {cartridge_name} Количество: {quantity}")
            return message.answer(f"В базе отрицательное количество!\
                                  \nID:{id}\
                                  \nШтрих-коды:{all_barcodes}\
                                  \nНаименование:{cartridge_name}\
                                  \nКоличество:{quantity}")
        
        # Фромируем строку для каждого картриджа
        line: str = f"{status_color}      <b>{cartridge_name}</b>\n"
        line += f"Количество:   <b>{quantity}</b> шт.\n"

        # Плодим еще сущности, потому что по-другому хз как вывести нормально..
        barcodes_list = all_barcodes.split("; ")
        for barcode in barcodes_list:
            line += f"Штрих-код:     <b>{barcode}</b>\n"

        line += f"Изменение:    <b>{last_update}</b>\n"
        line += f"ID в базе: <b>{id}</b>\n"
        text_lines.append(line)

    # Собираем полное сообщение из частей и отправляем его в ответ на команду /list
    full_text = header + "\n".join(text_lines)
    
    await message.answer(full_text, parse_mode="HTML")


@rt.message(Command("notice"))
async def notice(message: Message, command: CommandObject) -> Message | None:
    # Проверяем, что аргументы вообще есть
    if not command.args:
        return await message.answer("Команда включения уведомлений пользователям от ТСД требует аргументов.\n"
                                    "<b>/notice TG_ID ON_OFF</b>\n"
                                    "Параметр ON_OFF принимает только булевые 0 и 1, отвечает за включение и отключение уведомлений.\n"
                                    "Пример синтаксиса для включения уведомлений:\n"
                                    "<b>/notice 123456789 1</b>\n",
                                    parse_mode="HTML")
    
    # Проверка кол-ва аргументов, ожидается только ID(цифровая) и BOOL(булевая)
    parts: list[str] = command.args.split(maxsplit=1)
    if len(parts) != 2:
        return await message.answer("Неверное количество аргументво команды!")
    
    user_id_str, on_off_str = parts
    # Проверка на число
    if not user_id_str.isdigit():
        return await message.answer("ID должен состоять только из цифр!")
    # Проверка 
    if on_off_str not in ("0", "1"):
        return await message.answer("Параметр уведомлений может быть только 0 или 1!")
    
    # Проверяем есть ли вообще пользователь с таким ID в базе, если нет - выходим с сообщением, что такого пользователя нет.
    if await user_exists(user_id_str):
        await update_user_notice(
            telegram_id=int(user_id_str),
            notice_enabled=int(on_off_str),
        )
        await message.answer(f"Уведомления изменены на <b>{on_off_str}</b> \
                              \nПользователь с ID: <b>{user_id_str}</b>", parse_mode="HTML")
    else:
        return await message.answer(f"Пользователя с ID: {user_id_str} нет в базе!")


# Аналогичная функция по функционалу (как и в случае с ТСД) для обновления позиции количества картриджа в базе. 
# Надо потом как нибудь переделать покрасивее  
@rt.message(Command("renew"))
async def renew(message: Message, command: CommandObject, bot:Bot) -> Message | None:
    
    if not command.args:
        return await message.answer("Команда обновления количества картриджей в базе требует аргументов.\n"
                                "<b>/renew BARCODE CHANGE</b>\n"
                                "Параметр BARCODE принимает только штрих-код картриджа.\nПосмотреть все можно выведя список /list\n"
                                "Параметр CHANGE принимает положительные и отрицательные значения от -15 до 15.\n"
                                "Он определяет количество добавляемых картриджей в базу.\n\n"
                                "Пример синтаксиса для добавления 2 шт картриджа TL-420:\n"
                                "<b>/renew 123456789123 +2</b>\n",
                                parse_mode="HTML")

    # Нам нужно только два аргумента
    parts: list[str] = command.args.split(maxsplit=1)
    if len(parts) != 2:
        return await message.answer("Неверное количество аргументов команды!")
    barcode, change = parts

    # Простые проверки аргументов
    if not barcode.isdigit():
        return await message.answer("Штрих-код должен состоять только из цифр!")
    if not is_number(change):
        return await message.answer("Количество должно быть числом!")
    if not(-15 <= int(change) <= 15):
        return await message.answer("Количество должно быть от -15 до 15!")
    if int(change) == 0:
        return await message.answer("Какой в этом смысл?")
    

    # Список айдишек для метода бота send_message
    user_ids = await get_tg_id_list_notification()

    # Заготовка текста для answer
    msg_text: str = f"TG_ID: {message.from_user.id}         | Имя: {message.from_user.first_name}"

    # Вызываем функцию базы
    db_operation_res: tuple[int, str] | str = await update_cartridge(barcode, int(change))
    
    # Обработка db_operation_res
    # Если вернулся кортеж из (new_qty, name)
    # Отправляем уведомление в тг ВСЕМ кто в рассылке и логируем как инфо
    if isinstance(db_operation_res, tuple) and len(db_operation_res) == 2:
        balance, cartridge_name = db_operation_res
        logger.info(f"| TELEGRAM |   Обновлена БД  | Штрих-код: {barcode} | Имя: {cartridge_name} | Количество: {balance}")
        for user_id in user_ids:
            try:
                await bot.send_message(chat_id=user_id, 
                                       text=f"Выполнено!\
                                       \nШтрих-код: {barcode}\
                                       \nНаименование: {cartridge_name}\
                                       \nНовое количество: {balance}")
                
                logger.info(f"| TELEGRAM |    Доставлено   | " + msg_text)
            except Exception as e:
                logger.warning(f"| TELEGRAM |  Не доставлено  | "+ msg_text)
                return None
            return
        
    # Обработка db_operation_res
    # Если вернулась строка: NOT_FOUND:BARCODE или NO_STOCK:CARTRIDGE_NAME
    # Отправляем ОТВЕТ в тг и логируем как предупреждение
    elif isinstance(db_operation_res, str):
        barcode_or_name: str = db_operation_res.split(":", 1)[1]
        
        # Если не найден картридж по штриху в базе отправляем в лог и в тг-ответ
        if db_operation_res.startswith("NOT_FOUND:"):
            logger.warning(f"| TELEGRAM | Не обновлена БД | Не найден штрих-код: {barcode_or_name}")
            # Если не ушел ответ тоже логируем
            try:
                await message.answer(f"Операция не выполнена!\
                                     \nПричина: нет в базе.\
                                     \nШтрих-код: {barcode_or_name}")
            except Exception as e:
                logger.warning(f"| TELEGRAM | Не доставлено | "+ msg_text)
                return None
            logger.info(f"| TELEGRAM |    Доставлено   | " + msg_text)
            return
        
        # Если не получилось изменить количество в базе отправляем в лог и в тг-ответ
        if db_operation_res.startswith("NO_STOCK:"):
            logger.warning(f"| TELEGRAM | Не обновлена БД | Нет на складе или отрицательное количество: {barcode_or_name}")
            # Если не ушел ответ тоже логируем
            try:
                await message.answer(f"Операция не выполнена!\
                                     \nНаименование: {barcode_or_name} \
                                     \nПричина: нет на складе или \
                                     отрицательное количество после выполнения операции.\
                                    ")
            except Exception as e:
                logger.warning(f"| TELEGRAM | Не доставлено | "+ msg_text)
                return None
            logger.info(f"| TELEGRAM |    Доставлено   | "+ msg_text)
            return

    # Любой другой вариант это косяк update_cartridge()  — возвращаем 400
    else:       
        logger.error(f"| TELEGRAM | Ошибка БД | Вернула неожиданный результат: {db_operation_res}")
        for user_id in user_ids:
            return await bot.send_message(chat_id=user_id, text=f"Ошибка!\
                                                                \nНеожиданный ответ от БД.\
                                                                \nВернулось: {db_operation_res}")

# Хэндлер для вставки нового картриджа в базу.
@rt.message(Command("insert"))
async def insert(message: Message, command: CommandObject, bot:Bot) -> Message | None:
    
    if not command.args:
        return await message.answer("Команда добавления <b>нового</b> картриджа в таблицу.\n"
                                "<b>/insert BARCODE CARTRIDGE_NAME QUANTITY</b>\n"
                                "Параметр BARCODE принимает только штрих-код картриджа.\n"
                                "Параметр CARTRIDGE_NAME принимает строковое значение имени картриджа.\n"
                                "Имя НЕ ДОЛЖНО содержать пробелов, но ним дробятся аргументы.\n"
                                "Параметр QUANTITY принимает количество этого картриджа.\n\n"
                                "Пример синтаксиса для вставки в базу двух картриджей с именем new_cartridge:\n"
                                "<b>/insert 1234567891234 new_cartridge 2</b>\n",
                                parse_mode="HTML")

    # Нам нужно только 3 аргумента
    parts = command.args.split()
    if len(parts) != 3:
        return await message.answer("Неверное количество аргументов команды!")
    barcode, cartridge_name, quantity = parts

    # Проверки: имя проверять нет смысла, количество должно быть числом, штрих - строка состоящая из цифр
    if not barcode.isdigit():
        return await message.answer("Штрих-код должен состоять только из цифр!")
    if not is_number(quantity):
        return await message.answer("Количество должно быть числом!")
    if not(-15 <= int(quantity) <= 15):
        return await message.answer("Количество должно быть от -15 до 15!")

    # Две проверки:
    # Ищем по штрихкоду в базе
    search_res_by_barcode = await get_cartridge_by_barcode(barcode)
    # Ищем по имени в базе 
    search_res_by_name = await get_cartridge_by_name(cartridge_name)
    # обе переменные содержат кортеж (id, cartridge_name, all_barcodes, quantity, last_update)


    # Если одна из переменных содержит результат поиска (или обе), то нужно проверить все варианты
    # ЗАМЕТКА
    # any() используется для проверки, что в результате поиска есть хоть что-то.
    # Сейчас any() не нужен, но можно использовать если функции базы будут меняться.
    # Сейчас в sql запросах используется группировка GROUP BY c.id, и в случае "ненахода" будет возвращаться None, а не кортеж из нонов
    if search_res_by_barcode or search_res_by_name:
        
        # Обе что-то вернули, нужно сравнить айдишники картриджа, которые вернулись по штрихкоду и по имени
        if search_res_by_barcode and search_res_by_name:
            # Если айдишники совпали, значит в базе уже есть этот картридж с таким именем и штрихкодом
            # Можно отправить в вывод и search_res_by_barcode и search_res_by_name, они будут идентичные
            if search_res_by_barcode[0] == search_res_by_name[0]:
                line = f"ID картриджа у результатов поиска по штрих-коду и по имени совпал.\n"
                line += f"Картридж со штрих-кодом {barcode} и именем {cartridge_name} есть в базе.\n"
                line += f"\n"
                line += f"\nИмя: {search_res_by_barcode[1]}"
                line += f"\nКоличество: {search_res_by_barcode[3]}"

                barcodes_list = search_res_by_barcode[2].split("; ")
                for i in barcodes_list:
                    line += f"\nШтрих-код:     <b>{i}</b>"

                line += f"\nПоследнее изменение: {search_res_by_barcode[4]}"
                line += f"\nID в базе: {search_res_by_barcode[0]}"
                line += f"\n\nЕсли необходимо изменить количество по этому штрихкоду, используй команду /renew"    
                return await message.answer(f"{line}", parse_mode="HTML")
            
            # Если айдишники не совпали, значит переданные пользователем штрихкод и имя связаны в базе с разными айдишками картриджей.
            # Можно просто через else а не elif, но так нагляднее
            elif search_res_by_barcode[0] != search_res_by_name[0]:
                # Можно вывести инфу по обоим позициям для понимания
                line = f"ID картриджа у результатов поиска по штрих-коду и по имени не совпали!"
                line += f"\n\nВ базе штрих-код {barcode} связан с существующим картриджем."
                line += f"\nИмя:                  <b>{search_res_by_barcode[1]}</b>"
                line += f"\nКоличество:   {search_res_by_barcode[3]}"
                barcodes_list_1 = search_res_by_barcode[2].split("; ")
                for i in barcodes_list_1:
                    line += f"\nШтрих-код:     <b>{i}</b>"
                line += f"\nИзменение:    {search_res_by_barcode[4]}"
                line += f"\nID в базе:         {search_res_by_barcode[0]}"
                

                line += f"\n\nВ базе имя {cartridge_name} связано с существующим картриджем."
                line += f"\nИмя:                  <b>{search_res_by_name[1]}</b>"
                line += f"\nКоличество:   {search_res_by_name[3]}"

                barcodes_list_2 = search_res_by_name[2].split("; ")
                for i in barcodes_list_2:
                    line += f"\nШтрих-код:     <b>{i}</b>"

                line += f"\nИзменение:    {search_res_by_name[4]}"
                line += f"\nID в базе:         {search_res_by_name[0]}"
                line += f"\n\n\nЕсли необходимо изменить количество по этим позициям, используй команду /renew"
                return await message.answer(f"{line}", parse_mode="HTML")
        # Если вернулся только результат по штрихкоду, но не вернулся по имени, говорим об этом пользователю и выводим результат по штрихкоду
        if search_res_by_barcode:
            line = f"Картридж со штрих-кодом {barcode} уже есть в базе.\n"
            line += f"\nИмя: {search_res_by_barcode[1]}"
            line += f"\nКоличество: {search_res_by_barcode[3]}"

            barcodes_list = search_res_by_barcode[2].split("; ")
            for i in barcodes_list:
                line += f"\nШтрих-код:     <b>{i}</b>"

            line += f"\nПоследнее изменение: {search_res_by_barcode[4]}"
            line += f"\nID в базе: {search_res_by_barcode[0]}"
            line += f"\n\nЕсли необходимо изменить количество по этому штрихкоду, используй команду /renew"    
            return await message.answer(f"{line}", parse_mode="HTML")
        # Если вернулся только результат по имени, но не вернулся по штриху, говорим об этом пользователю и выводим результат по имени
        elif search_res_by_name:
            line = f"Картридж с именем {cartridge_name} уже есть в базе.\n"
            line += f"\nИмя: {search_res_by_name[1]}"
            line += f"\nКоличество: {search_res_by_name[3]}"

            barcodes_list = search_res_by_name[2].split("; ")
            for i in barcodes_list:
                line += f"\nШтрих-код:     <b>{i}</b>"

            line += f"\nПоследнее изменение: {search_res_by_name[4]}"
            line += f"\nID в базе: {search_res_by_name[0]}"
            line += f"\n\nЕсли необходимо изменить количество по этому имени, используй команду /renew"    
            return await message.answer(f"{line}", parse_mode="HTML")
    else:
        return await message.answer(f"Всё норм, в базе нет инфы по этим позициям", parse_mode="HTML")



    # Проверка: ищем по имени в базе, если найден - выходим с сообщением, что такое имя уже есть,
    # и нужно использовать другую функцию по обновлению количества, а не вставлять новый, иначе будет дублирование позиций

   
    # Вызываем функцию базы
