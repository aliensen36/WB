# keyboards/product_kb.py
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder


def get_products_management_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура для управления товарами"""
    builder = InlineKeyboardBuilder()

    builder.add(
        InlineKeyboardButton(text="📝 Изменить название товара", callback_data="edit_product_name"),
        InlineKeyboardButton(text="📋 Показать все товары", callback_data="show_all_products"),
        InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_settings")
    )
    builder.adjust(1)

    return builder.as_markup()


def get_cancel_inline_keyboard() -> InlineKeyboardMarkup:
    """Инлайн-клавиатура с кнопкой отмены"""
    builder = InlineKeyboardBuilder()
    builder.add(InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_operation"))
    return builder.as_markup()
