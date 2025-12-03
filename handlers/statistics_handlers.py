# handlers/statistics_handlers.py
from aiogram import Router, F
from aiogram.types import Message
import logging

from keyboards.statistics_kb import get_stats_keyboard

logger = logging.getLogger(__name__)

statistics_router = Router()


@statistics_router.message(F.text == "📊 Статистика")
async def handle_statistics_button(message: Message):
    """
    Обработчик кнопки '📊 Статистика'
    """
    keyboard = get_stats_keyboard()

    await message.answer(
        "📊 Выберите один из вариантов ниже:",
        reply_markup=keyboard
    )