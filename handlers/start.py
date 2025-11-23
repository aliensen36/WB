from aiogram.filters import Command
from aiogram import Router
from aiogram.types import Message

from keyboards.statistics_kb import get_main_keyboard

start_router = Router()

# Обработчик команды /start
@start_router.message(Command("start"))
async def cmd_start(message: Message):
    user_name = message.from_user.first_name or "друг"
    await message.answer(
        f"Привет, <b>{user_name}</b>! 👋\n\n"
        f"Я бот для анализа статистики Wildberries.\n"
        f"Выберите нужный раздел:",
        reply_markup=get_main_keyboard()
    )
