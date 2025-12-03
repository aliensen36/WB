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


def get_shops_management_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура для управления магазинами"""
    builder = InlineKeyboardBuilder()

    builder.add(
        InlineKeyboardButton(text="➕ Добавить магазин", callback_data="add_shop"),
        InlineKeyboardButton(text="✏️ Изменить название", callback_data="edit_shop"),
        InlineKeyboardButton(text="🗑 Удалить магазин", callback_data="delete_shop"),
        InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_settings")
    )
    builder.adjust(2, 1, 1)

    return builder.as_markup()


def get_products_management_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура для управления продуктами"""
    builder = InlineKeyboardBuilder()

    builder.add(
        InlineKeyboardButton(text="📋 Список продуктов", callback_data="products_list"),
        InlineKeyboardButton(text="✏️ Изменить названия", callback_data="edit_products"),
        InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_settings")
    )
    builder.adjust(2, 1)

    return builder.as_markup()


def get_back_to_settings_keyboard() -> InlineKeyboardMarkup:
    """Кнопка возврата в настройки"""
    builder = InlineKeyboardBuilder()
    builder.add(InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_settings"))
    return builder.as_markup()
