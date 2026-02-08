from aiogram import Bot, Dispatcher
from app.bot.token import TOKEN
from app.bot.handlers import rt


# Создем объект бот класса Бот
bot = Bot(token=TOKEN)

# Диспетчер - мозг бота, обработчик, который принимает события (сообщения, 
# команды и т.д.) и направляет их в роутеры или сразу в
# функции обработчики - хэндлеры 
dp = Dispatcher()

# Регистрируем роутер в диспетчере
dp.include_router(rt)