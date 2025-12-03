# run.py
import asyncio
import logging
from aiogram import Bot, Dispatcher, types
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from dotenv import load_dotenv
from config import config
from database.engine import drop_db, create_db, session_maker
from functions.scheduler import StatisticsScheduler
from functions.set_bot_commands import set_bot_commands
from handlers.account_handlers import account_router
from handlers.product_handlers import product_router
from handlers.settings_handlers import settings_router
from handlers.start_handlers import start_router
from handlers.statistics_handlers import statistics_router
from middlewares.chat_auth import ChatAuthMiddleware
from middlewares.db import DataBaseSession
from middlewares.errors import ErrorMiddleware

load_dotenv()

# Настройка логирования
logging.basicConfig(level=logging.INFO)

# Инициализация бота и диспетчера
bot = Bot(
    token=config.BOT_TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML)
)
dp = Dispatcher()


dp.include_router(start_router)
dp.include_router(account_router)
dp.include_router(statistics_router)
dp.include_router(settings_router)
dp.include_router(product_router)


# Создаем планировщик
scheduler = StatisticsScheduler(bot, session_maker, admin_chat_id=config.ADMIN_CHAT_ID)


async def on_startup(bot):
    await create_db()
    await set_bot_commands(bot)
    print("Бот запущен! https://t.me/WB_API_infobot")

    # Запускаем планировщик отчетов для админа
    asyncio.create_task(scheduler.start_scheduler())
    print("Планировщик отчетов запущен")


async def on_shutdown(bot):
    print('\nБот остановлен пользователем')


async def main():
    try:
        dp.startup.register(on_startup)
        dp.shutdown.register(on_shutdown)

        dp.update.outer_middleware(ErrorMiddleware())  # 1-й
        dp.update.outer_middleware(ChatAuthMiddleware(admin_chat_id=config.ADMIN_CHAT_ID))  # 2-й
        dp.update.outer_middleware(DataBaseSession(session_pool=session_maker))  #

        await bot.delete_webhook(drop_pending_updates=True)
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())

    except KeyboardInterrupt:
        print("\nБот остановлен пользователем (Ctrl+C)")
    except Exception as e:
        logging.error(f"Ошибка при запуске бота: {e}")
    finally:
        await bot.session.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Программа завершена")
