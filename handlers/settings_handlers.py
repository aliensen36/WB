# settings_handlers.py
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession
import logging

from database.account_manager import AccountManager
from keyboards.settings_kb import (
    get_settings_keyboard
)

logger = logging.getLogger(__name__)

settings_router = Router()


@settings_router.message(F.text == "⚙️ Настройки")
async def show_settings(message: Message, session: AsyncSession):
    """Показать главное меню настроек"""
    await message.answer("<b>Выберите раздел:</b>",
        reply_markup=get_settings_keyboard()
    )
