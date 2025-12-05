# statistics_kb.py
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton


def get_stats_keyboard() -> InlineKeyboardMarkup:
    """
    Создает инлайн-клавиатуру для выбора статистики
    Каждая кнопка размещается в отдельном ряду
    """
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text="📊 Текущая статистика",
                callback_data="current_stats"
            )
        ],
        [
            InlineKeyboardButton(
                text="📈 Статистика товаров за вчера",
                callback_data="yesterday_stats"
            )
        ]
    ])

    return keyboard