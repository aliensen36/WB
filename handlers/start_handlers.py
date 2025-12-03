# start_handlers.py

from aiogram.filters import Command
from aiogram import Router
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession
from database.user_manager import UserManager
from keyboards.main_kb import get_main_keyboard

start_router = Router()


@start_router.message(Command("start"))
async def cmd_start(message: Message, session: AsyncSession):
    try:
        # Создаем или обновляем пользователя в БД
        user_manager = UserManager(session)
        user = await user_manager.get_or_create_user(message.from_user)

        user_name = message.from_user.first_name or "друг"

        await message.answer(
            f"Привет, <b>{user_name}</b>! 👋\n\n"
            f"Я бот для анализа статистики Wildberries.\n\n"
            f"<b>Основные функции:</b>\n"
            f"• 📊 Статистика - просмотр статистики всех магазинов\n"
            f"• ⚙️ Настройки - управление магазинами и товарами\n\n"
            f"Выберите действие:",
            reply_markup=get_main_keyboard()
        )

    except Exception as e:
        print(f"❌ Ошибка в обработчике /start: {e}")
        await message.answer(
            "❌ Произошла ошибка при запуске бота. Попробуйте позже.",
            reply_markup=get_main_keyboard()
        )
