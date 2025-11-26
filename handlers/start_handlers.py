from aiogram.filters import Command
from aiogram import Router
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession
from database.account_manager import AccountManager
from database.user_manager import UserManager
from keyboards.account_kb import get_accounts_keyboard, get_main_accounts_keyboard
from keyboards.statistics_kb import get_main_keyboard

start_router = Router()


@start_router.message(Command("start"))
async def cmd_start(message: Message, session: AsyncSession):
    try:
        # Создаем или обновляем пользователя в БД
        user_manager = UserManager(session)
        user = await user_manager.get_or_create_user(message.from_user)

        # Получаем ВСЕ кабинеты
        account_manager = AccountManager(session)
        all_accounts = await account_manager.get_all_accounts()

        user_name = message.from_user.first_name or "друг"

        if all_accounts:
            # Есть кабинеты - показываем клавиатуру с кабинетами
            await message.answer(
                f"Привет, <b>{user_name}</b>! 👋\n\n"
                f"Я бот для анализа статистики Wildberries.\n"
                f"Доступные кабинеты:",
                reply_markup=get_accounts_keyboard(all_accounts)
            )
        else:
            # Нет кабинетов - показываем основную клавиатуру
            await message.answer(
                f"Привет, <b>{user_name}</b>! 👋\n\n"
                f"Я бот для анализа статистики Wildberries.\n\n"
                f"📋 <b>Пока нет добавленных кабинетов</b>\n"
                f"Давайте добавим первый кабинет продавца!",
                reply_markup=get_main_accounts_keyboard()
            )

    except Exception as e:
        print(f"❌ Ошибка в обработчике /start: {e}")
        await message.answer(
            "❌ Произошла ошибка при запуске бота. Попробуйте позже."
        )