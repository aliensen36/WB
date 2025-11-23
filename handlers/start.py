from aiogram.filters import Command
from aiogram import Router
from aiogram.types import Message

start_router = Router()

# Обработчик команды /start
@start_router.message(Command("start"))
async def cmd_start(message: Message):
    await message.answer(
        "Привет! Я бот на aiogram 3!\n"
        "Используй /help для списка команд"
    )