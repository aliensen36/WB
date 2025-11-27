# settings_kb.py
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton


def get_settings_keyboard() -> InlineKeyboardMarkup:
    """Инлайн-клавиатура для настроек"""
    from aiogram.utils.keyboard import InlineKeyboardBuilder

    builder = InlineKeyboardBuilder()
    builder.add(
        InlineKeyboardButton(text="➕ Добавить магазин", callback_data="add_shop"),
        InlineKeyboardButton(text="🗑 Удалить магазин", callback_data="delete_shop")
    )
    builder.adjust(1)
    return builder.as_markup()
