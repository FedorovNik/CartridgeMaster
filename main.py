
import asyncio
import logging
import socket
import signal
from app.bot.bot_init import bot, dp
from app.web.web_logic import create_web_app
from app.database.db_operations import create_tables
from aiohttp import web

hostname = socket.gethostname()
local_ip = socket.gethostbyname(hostname)


async def main():
    # Логи на серверной части должны быть красивыми и информативными, чтобы было удобно
    # отлаживать и понимать что происходит.
    logger = logging.getLogger(__name__)
    logging.basicConfig(
        # %(name)-15s — зарезервировать 15 символов под имя логгера и выровнять по левому краю (-)
        # %(levelname)-8s — зарезервировать 8 символов под уровень (INFO, ERROR и т.д.)
        format='%(asctime)s - %(name)-18s - %(levelname)-7s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S',
        level=logging.INFO
    )
    logger.info(f"Имя хоста: {hostname}")
    logger.info(f"IP-адрес:  {local_ip}")

    ################################### ИНИЦИАЛИЗАЦИЯ БАЗЫ ДАННЫХ ###########################################
    try:
        await create_tables()
    except Exception:
        logger.exception("Ошибка при инициализации базы данных!")
    finally:
        logger.info(f"Инициализация sqlite БД успешно проведена.")


    ################################### ИНИЦИАЛИЗАЦИЯ ЛОКАЛЬНОГО ВЕБ СЕРВЕРА ################################
    try:
        # Передаем веб-приложению с веб-сервером объект бота, для того чтобы 
        # из него можно было просто отправлять сообщения в тг
        web_app = await create_web_app(bot)

        # Создаем движок (ранер) для запуска сайта в веб-приложении, и делаем для него кастомное имя в логах.
        # custom_access_logger просто для красоты и на функционал не влияет.
        # Без этого в сервер-логе будет отображаться как aiohttp.access и дублироваться дата
        custom_access_logger = logging.getLogger("aiohttp.access.log")
        web_runner = web.AppRunner(
            web_app, 
            access_log=custom_access_logger,
            access_log_format='%a "%r" %s' # IP, Запрос, Статус
        )
        await web_runner.setup()
    except Exception:
        logger.exception("Ошибка при инициализации веб-сервера!")
        return
    else:
        logger.info(f"Веб-сервер запущен и доступен по адресу http://{local_ip}:8080/scan")
        # Запускаем веб-приложение (в фоне), указываем ему слушать всё на 8080 порту
        site = web.TCPSite(web_runner, '0.0.0.0', 8080)
        await site.start()


    ########################### ЗАПУСК ПУЛИНГА БОТА И ОБРАБОТКА СИГНАЛОВ ОСТАНОВКИ ##########################
    
    # Создаем event для остановки
    loop = asyncio.get_running_loop()
    stop_event = asyncio.Event()

    def _on_stop():
        logger.info("Получен сигнал остановки - запуск процедуры завершения.")
        loop.call_soon_threadsafe(stop_event.set)

    # Попытаемся зарегистрировать обработчики сигналов — на винде add_signal_handler может быть не реализован
    for sig in (signal.SIGINT, signal.SIGTERM):

        # Регистрируем нормальный обработчик сигнала для корректной остановки сервера и бота при получении SIGINT (Ctrl+C) или SIGTERM
        # Выполнится на линухе нормально.
        try:
            loop.add_signal_handler(sig, _on_stop)
            logger.info(f"Регистрация обработчика сигнала останова {sig.name} ({sig.value}) завершена.")

        # Если платформа (Windows!!!!!) не поддерживает add_signal_handler, то надо ловить исключение NotImplementedError и использовать signal.signal
        # питон на Windows лишь имитирует поведение сигналов, костыль не идеальный, но лучше чем ничего. 
        # На практике это означает, что при нажатии Ctrl+C будет вызван обработчик _on_stop, который запустит процедуру корректной остановки.
        except NotImplementedError:
            signal.signal(sig, lambda s, f: _on_stop())
            logger.info(f"Регистрация обработчика сигнала останова {sig.name} ({sig.value}) завершена.")

    
    # Запускаем polling в фоне и запрещаем aiogram регистрировать сигналы,
    # Иначе миллион исключений при попытке поймать сигнал остановки
    polling_task = asyncio.create_task(dp.start_polling(bot, handle_signals=False))

    try:
        # Ожидание сигнала остановки
        await stop_event.wait()
        logger.info("Выполняется запрос диспетчеру на корректную остановку пулинга.")
        # Просим диспетчер корректно остановить пулинг
        try:
            await dp.stop_polling()
        except Exception:
            logger.exception("Ошибка при вызове метода диспетчера stop_polling!")

        # Ожидание завершения фонового таска пулинга, с обработкой исключения CancelledError,
        # которое будет выброшено при остановке пулинга.
        try:
            await polling_task
        except asyncio.CancelledError:
            pass
    # Вряд ли вызовется, но пусть будет для отлавливания неожиданных исключений в основном цикле
    except Exception:
        logger.exception("Критическая ошибка в основном цикле!")

    finally:
        # Нормально закрываем веб-сервак, очищая ресурсы
        try:
            await web_runner.cleanup()
        except Exception:
            logger.exception("Ошибка при остановке веб-сервера!")
        else:
            logger.info(f"Веб-сервер успешно остановлен.")

        # Нормально закрываем сессию бота
        try:
            await bot.session.close()
        except Exception:
            logger.exception("Ошибка при закрытии сессии бота!")
    

if __name__ == '__main__':
    #try:
    asyncio.run(main())
    # Небольшая обработка прерываний клавиатуры потом убрать
    #except KeyboardInterrupt:
    #    print('Keyboard interrupt: Ctrl+C')