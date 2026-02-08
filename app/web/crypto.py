import os, logging

import base64
from Crypto.Cipher import AES
from Crypto.Util.Padding import unpad, pad

logger = logging.getLogger(__name__)

# Ключ по которому будет шифровать сырой http трафик, чтобы защитить базу от складских хакеров
AES_KEY = "My_Secret_Key_16".encode('utf-8') 

# Вызывается из handle_tsd_scan для расшифровки POST запроса ТСД в виде AES Base64 строки
def decrypt_data(encrypted_b64):
    try:
        # Декодируем из Base64 в байты
        raw = base64.b64decode(encrypted_b64)
        # Вырезаем IV (первые 16 байт) и само сообщение
        iv = raw[:16]
        ciphertext = raw[16:]
        # Настраиваем дешифратор
        cipher = AES.new(AES_KEY, AES.MODE_CBC, iv)
        # Расшифровываем и убираем падинги
        decrypted = unpad(cipher.decrypt(ciphertext), AES.block_size)
        return decrypted.decode('utf-8')
    except Exception as e:
        logging.error(f"ServerLog: исключение функции дешифратора!{e}")
        return None


# Вызывается из handle_tsd_scan для шифровки ответа сервера для ТСД в AES Base64 строку
def encrypt_data(plaintext):
    try:
        # Преобразуем текст в байты
        plaintext_bytes = plaintext.encode('utf-8')
        # Генерируем случайный IV (16 байт)
        iv = os.urandom(16)
        # Передаем шифратору ключ и IV и режим шифрования
        cipher = AES.new(AES_KEY, AES.MODE_CBC, iv)
        # Добавляем падинги, т.к. АЕS работает с блоками фиксированного размера 16 байт. 
        # Нужно дополнить до 16 кратного размера
        padded = pad(plaintext_bytes, AES.block_size)
        ciphertext = cipher.encrypt(padded)
        # Объединяем IV + зашифрованные данные и кодируем в Base64
        encrypted = base64.b64encode(iv + ciphertext)
        return encrypted.decode('utf-8')
    except Exception as e:
        logging.error(f"ServerLog: исключение функции шифратора!{e}")
        return None