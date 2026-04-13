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
        message.attach(MIMEText(body, "html"))
        
        text = message.as_string()
        server.sendmail(email_address, recipient, text)
        server.quit()
        
        logger.info(f"'EMAIL: Уведомление отправлено на {recipient}'")
        return True
    except Exception as e:
        logger.error(f"'EMAIL: Ошибка при отправке на {recipient}: {e}'")
        return False


import asyncio
from concurrent.futures import ThreadPoolExecutor
import logging

logger = logging.getLogger(__name__)

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
    
    # Формируем HTML-тело письма
    html_body = """
    <html>
    <head>
        <style>
            body { font-family: Arial, sans-serif; color: #333333; }
            .header { color: #2c3e50; }
            table { border-collapse: collapse; width: 100%; max-width: 600px; margin-top: 15px; }
            th, td { border: 1px solid #dddddd; padding: 10px; text-align: left; }
            th { background-color: #f4f4f4; font-weight: bold; }
            .qty-alert { color: #d9534f; font-weight: bold; }
            .footer { margin-top: 25px; font-size: 0.85em; color: #777777; }
        </style>
    </head>
    <body>
        <h3 class="header">Список расходников для закупки:</h3>
        <table>
            <thead>
                <tr>
                    <th>Модель</th>
                    <th>Текущее количество</th>
                    <th>Необходимый минимум</th>
                </tr>
            </thead>
            <tbody>
    """
    
    # Добавляем строки таблицы для каждого картриджа
    for cartridge in low_stock_cartridges:
        html_body += f"""
                <tr>
                    <td>{cartridge['name']}</td>
                    <td class="qty-alert">{cartridge['quantity']}</td>
                    <td>{cartridge['min_qty']}</td>
                </tr>
        """
        
    html_body += """
            </tbody>
        </table>
        <div class="footer">
            <p>Это уведомление сформировано автоматически, не отвечайте на него =)</p>
        </div>
    </body>
    </html>
    """
    
    subject = "CartridgeMaster: отчёт о состоянии расходных материалов"
    sent_count = 0
    
    try:
        # Используем ThreadPoolExecutor для запуска синхронного SMTP кода в отдельных потоках
        loop = asyncio.get_event_loop()
        executor = ThreadPoolExecutor(max_workers=5)
        
        tasks = []
        for recipient in emails:
            # Передаем html_body вместо обычного текста
            task = loop.run_in_executor(executor, _send_email_sync, recipient, subject, html_body)
            tasks.append(task)
        
        results = await asyncio.gather(*tasks)
        sent_count = sum(1 for result in results if result)
        
    except Exception as e:
        logger.error(f"Ошибка при отправке уведомлений: {e}")
        return 0
    
    return sent_count

