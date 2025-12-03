# settings_kb.py
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder


def get_settings_keyboard() -> InlineKeyboardMarkup:
    """Инлайн-клавиатура для настроек магазинов"""
    builder = InlineKeyboardBuilder()

    builder.row(
        InlineKeyboardButton(text="🏪 Управление магазинами", callback_data="manage_shops")
    )
    builder.row(
        InlineKeyboardButton(text="📦 Управление товарами", callback_data="manage_products")
    )
    return builder.as_markup()
