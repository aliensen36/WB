# keyboards/account_kb.py
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder


def get_shops_management_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура для управления магазинами"""
    builder = InlineKeyboardBuilder()

    builder.add(
        InlineKeyboardButton(text="➕ Добавить магазин", callback_data="add_shop"),
        InlineKeyboardButton(text="✏️ Изменить название", callback_data="edit_shop"),
        InlineKeyboardButton(text="🗑 Удалить магазин", callback_data="delete_shop"),
        InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_settings")
    )
    builder.adjust(1)

    return builder.as_markup()


def get_cancel_inline_keyboard() -> InlineKeyboardMarkup:
    """Создает инлайн-клавиатуру с кнопкой отмены"""
    builder = InlineKeyboardBuilder()
    builder.add(InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_operation"))
    return builder.as_markup()
