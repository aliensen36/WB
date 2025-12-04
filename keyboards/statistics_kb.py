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
                text="📈 Статистика за вчера",
                callback_data="yesterday_stats"
            )
        ],
        [
            InlineKeyboardButton(
                text="⚡ Быстрая сводка за сегодня",
                callback_data="today_quick_stats"
            )
        ]
    ])

    return keyboard