import asyncio
import logging
import os

from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from dotenv import load_dotenv
from config import config
from handlers.start import start_router

load_dotenv()

# Настройка логирования
logging.basicConfig(level=logging.INFO)

# Инициализация бота и диспетчера
bot = Bot(token=config.BOT_TOKEN)
dp = Dispatcher()

dp.include_router(start_router)


# Главная функция
async def main():
    try:
        print("Бот запущен! https://t.me/WB_API_infobot")
        await dp.start_polling(bot)
    except Exception as e:
        logging.error(f"Ошибка при работе бота: {e}")
    finally:
        await shutdown(dp, bot)

async def shutdown(dispatcher: Dispatcher, bot: Bot):
    await dispatcher.storage.close()
    await bot.session.close()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nБот остановлен пользователем")
    except Exception as e:
        logging.error(f"Критическая ошибка: {e}")

