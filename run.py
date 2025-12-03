# run.py
import asyncio
import logging
import subprocess
import sys
from pathlib import Path
from aiogram import Bot, Dispatcher, types
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from dotenv import load_dotenv
from config import config
from database.engine import drop_db, create_db, session_maker
from functions.scheduler import StatisticsScheduler
from functions.set_bot_commands import set_bot_commands
from handlers.accounts_settings_handlers import accounts_settings_router
from handlers.current_statistics_handlers import current_statistics_router
from handlers.product_statistics_handlers import product_statistics_router
from handlers.products_settings_handlers import products_settings_router
from handlers.settings_handlers import settings_router
from handlers.start_handlers import start_router
from handlers.statistics_handlers import statistics_router
from middlewares.chat_auth import ChatAuthMiddleware
from middlewares.db import DataBaseSession
from middlewares.errors import ErrorMiddleware

load_dotenv()

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('bot.log'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)

# Инициализация бота и диспетчера
bot = Bot(
    token=config.BOT_TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML)
)
dp = Dispatcher()

dp.include_router(start_router)
dp.include_router(statistics_router)
dp.include_router(settings_router)
dp.include_router(product_statistics_router)
dp.include_router(current_statistics_router)
dp.include_router(accounts_settings_router)
dp.include_router(products_settings_router)

# Создаем планировщик
scheduler = StatisticsScheduler(bot, session_maker, admin_chat_id=config.ADMIN_CHAT_ID)


async def run_alembic_migrations():
    """Запускает миграции Alembic перед стартом бота"""
    logger.info("Проверяю и применяю миграции базы данных...")

    try:
        # Получаем путь к корневой директории проекта
        project_root = Path(__file__).parent

        # Проверяем наличие файла alembic.ini
        alembic_ini_path = project_root / "alembic.ini"
        if not alembic_ini_path.exists():
            logger.warning("Файл alembic.ini не найден. Пропускаю миграции.")
            return True

        # Проверяем наличие директории миграций
        alembic_versions_path = project_root / "alembic" / "versions"
        if not alembic_versions_path.exists():
            logger.warning("Директория миграций не найдена. Создаю начальную миграцию...")
            try:
                # Создаем начальную миграцию если ее нет
                result = subprocess.run(
                    [sys.executable, "-m", "alembic", "revision", "--autogenerate", "-m", "initial"],
                    cwd=project_root,
                    capture_output=True,
                    text=True,
                    timeout=30
                )
                if result.returncode != 0:
                    logger.warning(f"Не удалось создать начальную миграцию: {result.stderr}")
            except Exception as e:
                logger.warning(f"Ошибка при создании начальной миграции: {e}")

        # Запускаем команду alembic upgrade head
        logger.info("Применяю миграции...")
        result = subprocess.run(
            [sys.executable, "-m", "alembic", "upgrade", "head"],
            cwd=project_root,
            capture_output=True,
            text=True,
            timeout=60  # Увеличиваем таймаут для миграций
        )

        if result.returncode == 0:
            if result.stdout:
                logger.info(f"Миграции успешно применены:\n{result.stdout.strip()}")
            else:
                logger.info("База данных уже актуальна")
            return True
        else:
            logger.error(f"Ошибка при применении миграций:")
            if result.stderr:
                logger.error(f"STDERR: {result.stderr}")
            if result.stdout:
                logger.error(f"STDOUT: {result.stdout}")
            return False

    except subprocess.TimeoutExpired:
        logger.error("Таймаут при выполнении миграций (более 60 секунд)")
        return False
    except FileNotFoundError:
        logger.error("Не найден alembic. Убедитесь, что alembic установлен в virtualenv")
        return False
    except Exception as e:
        logger.error(f"Непредвиденная ошибка при запуске миграций: {e}")
        return False


async def on_startup(bot):
    """Действия при запуске бота"""
    logger.info("Запуск бота...")

    # 1. Сначала создаем/проверяем структуру БД
    logger.info("Создаю структуру базы данных...")
    try:
        await create_db()
        logger.info("Структура базы данных создана/проверена")
    except Exception as e:
        logger.error(f"Ошибка при создании структуры БД: {e}")

    # 2. Запускаем миграции Alembic
    migrations_success = await run_alembic_migrations()

    if not migrations_success:
        logger.warning("Миграции не выполнены, но продолжаю запуск бота")
    else:
        logger.info("Все миграции успешно применены")

    # 3. Устанавливаем команды бота
    logger.info("Устанавливаю команды бота...")
    try:
        await set_bot_commands(bot)
        logger.info("Команды бота установлены")
    except Exception as e:
        logger.error(f"Ошибка при установке команд: {e}")

    # 4. Запускаем планировщик отчетов
    logger.info("Запускаю планировщик отчетов...")
    try:
        asyncio.create_task(scheduler.start_scheduler())
        logger.info("Планировщик отчетов запущен")
    except Exception as e:
        logger.error(f"Ошибка при запуске планировщика: {e}")

    # 5. Выводим информацию о боте
    bot_info = await bot.get_me()
    logger.info(f"Бот запущен: @{bot_info.username}")
    logger.info(f"Ссылка на бота: https://t.me/{bot_info.username}")
    logger.info(f"Админ чат ID: {config.ADMIN_CHAT_ID}")

    print("\n" + "=" * 50)
    print("Бот успешно запущен!")
    print(f"Имя бота: @{bot_info.username}")
    print(f"Ссылка: https://t.me/{bot_info.username}")
    print("=" * 50 + "\n")


async def on_shutdown(bot):
    """Действия при остановке бота"""
    logger.info("Остановка бота...")

    # Закрываем все соединения
    try:
        await bot.session.close()
        logger.info("Сессии бота закрыты")
    except Exception as e:
        logger.error(f"Ошибка при закрытии сессий: {e}")

    print("\nБот остановлен")


async def main():
    """Основная функция запуска бота"""
    try:
        # Регистрируем обработчики запуска и остановки
        dp.startup.register(on_startup)
        dp.shutdown.register(on_shutdown)

        # Настраиваем middleware
        dp.update.outer_middleware(ErrorMiddleware())  # 1-й
        dp.update.outer_middleware(ChatAuthMiddleware(admin_chat_id=config.ADMIN_CHAT_ID))  # 2-й
        dp.update.outer_middleware(DataBaseSession(session_pool=session_maker))  # 3-й

        # Удаляем вебхук и начинаем polling
        logger.info("Удаляю вебхук и начинаю polling...")
        await bot.delete_webhook(drop_pending_updates=True)

        logger.info("Начинаю прослушивание сообщений...")
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())

    except KeyboardInterrupt:
        logger.info("Бот остановлен пользователем (Ctrl+C)")
    except Exception as e:
        logger.error(f"Критическая ошибка при запуске бота: {e}", exc_info=True)
    finally:
        # Гарантированное выполнение при выходе
        await on_shutdown(bot)


if __name__ == "__main__":
    # Проверяем наличие необходимых переменных окружения
    if not config.BOT_TOKEN:
        logger.error("BOT_TOKEN не найден в переменных окружения")
        sys.exit(1)

    if not config.ADMIN_CHAT_ID:
        logger.warning("ADMIN_CHAT_ID не найден. Некоторые функции могут не работать.")

    # Запускаем бота с обработкой исключений
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nПрограмма завершена пользователем")
    except Exception as e:
        logger.error(f"Непредвиденная ошибка: {e}", exc_info=True)
        sys.exit(1)
