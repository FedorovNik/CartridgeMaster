# Этот модуль содержит основную логику обработки запросов от ТСД, взаимодействия с базой данных и отправки уведомлений в Telegram.
# Используется в основном для обработки POST-запросов от андроид-приложения, которое работает на ТСД. 
# Функция create_web_app вызывается из main.py, при инициализации сервера
# Работающий Веб-сервер при получении post запроса (в json формате) вызывает функцию handle_tsd_scan и происходит обработка:
#   1) Дешифровка полученных данных от ТСД (они приходят в виде AES Base64 строки)
#   2) Проверка данных на валидность (наличие нужных полей, правильный формат)
#   3) Взаимодействие с базой данных: обновление количества картриджей и получение информации о них
#   4) Отправка уведомлений в Telegram о том, что произошло с картриджем (добавлен, удален, не найден, нет на складе)
# Памятка стандартных возвращаемых кодов HTTP:
# 200 — OK: запрос успешно обработан
# 400 — Bad Request: неверный запрос - нарушен синтаксис
# 403 — Forbidden: отказ в доступе
# 404 — Fot Found: сервер не может найти данные по запросу
# 409 - Conflict: конфликт с состоянием ресурса (попытка уменьшить при нуле)

from aiohttp import web
import json, logging

# Функции для работы с базой
from app.database.db_operations import update_cartridge_count, get_tg_id_list_notification

# Фукнции шифрования json данных для обмена с ТСД по http.
from app.web.crypto import decrypt_data, encrypt_data

# Инициализация логгера для этого модуля
# Удобно для отладки - какой модуль отправил лог.
logger = logging.getLogger(__name__)

# Создание веб-приложения и настройка маршрута, вызывается из main.py при инициализации сервера
async def create_web_app(bot_instance):
    app = web.Application()
    # Кладем бота в состояние сервера, чтобы потом в обработчике handle_tsd_scan
    # можно было его удобно достать и отправлять сообщения в тг
    app['bot'] = bot_instance 
    app.router.add_post('/scan', handle_tsd_scan)
    return app


# Основная логика обработки POST-запросов от ТСД.
async def handle_tsd_scan(request):
    bot = request.app['bot'] # Достаем бота из состояния приложения

    ############################################ БЛОК ШИФРОВАНИЯ ################################################
    # Получаем кракозябры из тела запроса
    encrypted_payload = await request.text()
    # Превращаем кашу в читаемую строку
    decrypted_string = decrypt_data(encrypted_payload)
    # Проверяем расшифровалась ли переданная строка
    if not decrypted_string:
        logger.warning(f"Указан неверный ключ шифрования или получены неожиданные данные с IP: {request.remote}")
        # Отвечаем тсдшнику, отказ в доступе с кодом 403
        error_response = encrypt_data("Указан неверный ключ шифрования или получены неожиданные данные!")
        return web.Response(text=error_response, status=403)
    # Превращаем расшифрованную строку в JSON-словарь
    try:
        data = json.loads(decrypted_string)
    # Ловим исключение не проебались ли нигде json скобочки и тд
    except json.JSONDecodeError:
        error_response = encrypt_data("Критическое исключение, ошибка json-декодирования на стороне сервера")
        return web.Response(text=error_response, status=400)
    ################################### КОНЕЦ БЛОКА С ШИФРОВАНИЕМ ################################################

    ####################################### БЛОК ПРОВЕРОК ########################################################
    # Логируем весь полученный JSON в консоль
    logger.info(f"|    ТСД   |   Получен JSON  | Расшировка: {data}")

    # Базовая проверка на существование полей barcode и action в полученном JSON
    if "barcode" not in data or "action" not in data:
        # Если косяк то логируем и отвечаем ошибкой 400
        logger.warning("Неверный json-формат, поле barcode или action отсутствует!")
        error_response = encrypt_data("Неверный json-формат, поле barcode или action отсутствует!")
        return web.Response(text=error_response, status=400)
    # Простая проверка пройдена, заносим значения в переменные и проверяем дальше
    barcode = data["barcode"]
    action = data["action"]

    # Проверка barcode на строку, содержатся ли только цифры и длина штрих-кода картриджа = 13
    if not isinstance(barcode, str) or not barcode.isdigit() or not(len(barcode) == 13):
        # Лог в консоль и ответ с ошибкой 400
        logger.warning(f"Неверный json-формат. Поле barcode должно содержать только 13 цифр: {barcode}")
        error_response = encrypt_data("Неверный json-формат. Поле barcode должно содержать только 13 цифр!")
        return web.Response(text=error_response, status=400)

    # Проверка action: только строка "add" или "red"
    if action not in ["add", "red"]:
        # Лог в консоль и ответ с ошибкой 400
        logger.warning(f"Неверный json-формат. Поле action принимает только строку add или red: {action}")
        error_response = encrypt_data("Неверный json-формат. Поле action принимает только строку add или red!")
        return web.Response(text=error_response, status=400)
    # Проверка пройдена, action валиден, прибавляем или забираем картридж
    change = 1 if action == "add" else -1
    ###################################### КОНЕЦ БЛОКА ПРОВЕРОК ##################################################


    ###################################### ОПЕРАЦИИ с БД И ОТВЕТЫ ################################################
    # Асинхронно дергаем функцию обновления базы, передаем штрихкод и изменение количества
    # Вернется кортеж (new_qty, name) если обновление прошло успешно, или строка с сигналом об ошибке вида NOT_FOUND:barcode или NO_STOCK:barcode
    db_operation_res = await update_cartridge(barcode, change)

    # Список айдишников из базы пользователей для отправки уведомлений в тг
    user_ids = await get_tg_id_list_notification()

    # Обрабатываем результат: если вернулся кортеж из 2 элементов:
    if isinstance(db_operation_res, tuple) and len(db_operation_res) == 2:
        new_qty, name = db_operation_res
        logger.info(f"|    ТСД   |   Обновлена БД  | Штрих-код: {barcode} | Имя: {name} | Количество: {new_qty}")

        # Отправляем уведомление response_text в Telegram о успешном обновлении
        response_text = f"Штрих-код: {barcode}\nИмя: {name}\nДействие: {action}\nКоличество: {new_qty}"
        for user_id in user_ids:
            await bot.send_message(chat_id=user_id, text=f"{response_text}")

        # Ответ ТСД с кодом 200 и сообщением response_text
        encrypted_response = encrypt_data(response_text)
        return web.Response(text=encrypted_response, status=200)
    

    # Если вернулась строка — это сигналы вида NOT_FOUND:BARCODE или NO_STOCK:CARTRIDGE_NAME
    if isinstance(db_operation_res, str):
        if db_operation_res.startswith("NOT_FOUND:"):
            # После NOT_FOUND: всегда будет штрих-код. 
            # Можно взять его и скопировать в barcode_not_found или barcode, который распарсили из json в запросе от ТСД, по факту не важно.
            barcode_not_found = db_operation_res.split(":", 1)[1]
            logger.warning(f"|    ТСД   | Не обновлена БД | Не найден штрих-код в базе: {barcode_not_found}")
            
            # 404 Требуемый ресурс не найден, отвечаем только ТСД
            response_text = f"Нет в базе: {barcode_not_found}"
            encrypted_response = encrypt_data(response_text)
            return web.Response(text=encrypted_response, status=404)

        if db_operation_res.startswith("NO_STOCK:"):
            # После NO_STOCK: всегда будет имя картриджа, у которого закончился или закончится запас после запрошенной операции.
            # В barcode_no_stock заносим имя картриджа
            barcode_no_stock = db_operation_res.split(":", 1)[1]
            logger.warning(f"|    ТСД   | Не обновлена БД | Нет на складе или <0 после операции: {barcode_no_stock}")

            # 409 Кофликт с состоянием базы, отвечаем только ТСД
            response_text = f"Нет на складе или <0 после операции!\nШтрих-код: {barcode_no_stock}"
            encrypted_response = encrypt_data(response_text)
            return web.Response(text=encrypted_response, status=409)

        # Любой другой вариант — логируем, пишем в телегу и возвращаем 400 ТСД-шнику, но это вряд ли произойдет
        logger.error(f"|   ТСД    |   Ошибка БД     | Вернула неожиданный результат: {db_operation_res}")
        response_text = "Неожиданный ответ от БД!"
        for user_id in user_ids:
            await bot.send_message(chat_id=user_id, text=f"Штрих-код: {barcode}\nДействие: {action}\n{response_text}")

        encrypted_response = encrypt_data(response_text)
        return web.Response(text=encrypted_response, status=400)
    ###################################### КОНЕЦ ОПЕРАЦИЙ с БД И ОТВЕТОВ ##########################################

