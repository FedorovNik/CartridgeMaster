import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import logging
import asyncio
from concurrent.futures import ThreadPoolExecutor

from config import SMTP_SERVER, SMTP_PORT, EMAIL_ADDRESS, EMAIL_PASSWORD

logger = logging.getLogger("my_custom_logger")

# Настройки почтового сервера теперь импортируются из config.py
smtp_server = SMTP_SERVER
smtp_port = SMTP_PORT
email_address = EMAIL_ADDRESS
email_password = EMAIL_PASSWORD


def _send_email_sync(recipient, subject, body):
    """
    Синхронная функция для отправки одного письма
    """
    try:
        server = smtplib.SMTP_SSL(smtp_server, smtp_port)
        server.login(email_address, email_password)
        
        message = MIMEMultipart()
        message["From"] = email_address
        message["To"] = recipient
        message["Subject"] = subject
        message.attach(MIMEText(body, "plain"))
        
        text = message.as_string()
        server.sendmail(email_address, recipient, text)
        server.quit()
        
        logger.info(f"Уведомление отправлено на {recipient}")
        return True
    except Exception as e:
        logger.error(f"Ошибка при отправке на {recipient}: {e}")
        return False


async def send_low_stock_notifications(emails: list, low_stock_cartridges: list):
    """
    Отправляет уведомления о низком запасе картриджей на список email адресов
    
    Args:
        emails: Список email адресов для отправки
        low_stock_cartridges: Список картриджей с низким запасом
        
    Returns:
        Количество успешно отправленных уведомлений
    """
    if not emails or not low_stock_cartridges:
        return 0
    
    # Создаем тело письма
    body_lines = ["Уведомление о низком запасе картриджей:\n"]
    for cartridge in low_stock_cartridges:
        body_lines.append(f"- {cartridge['name']}: {cartridge['quantity']} шт. (мин: {cartridge['min_qty']} шт.)")
    
    body = "\n".join(body_lines)
    subject = "Уведомление о низком запасе картриджей"
    
    sent_count = 0
    
    try:
        # Используем ThreadPoolExecutor для запуска синхронного SMTP кода в отдельных потоках
        loop = asyncio.get_event_loop()
        executor = ThreadPoolExecutor(max_workers=5)
        
        tasks = []
        for recipient in emails:
            task = loop.run_in_executor(executor, _send_email_sync, recipient, subject, body)
            tasks.append(task)
        
        results = await asyncio.gather(*tasks)
        sent_count = sum(1 for result in results if result)
        
    except Exception as e:
        logger.error(f"Ошибка при отправке уведомлений: {e}")
        return 0
    
    return sent_count

