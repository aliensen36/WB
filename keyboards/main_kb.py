# main_kb.py
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton


def get_main_keyboard() -> ReplyKeyboardMarkup:
    """Главная реплай-клавиатура с двумя кнопками"""
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📊 Статистика"),
             KeyboardButton(text="📦 Статистика по товарам"),
             KeyboardButton(text="⚙️ Настройки")]
        ],
        resize_keyboard=True,
        input_field_placeholder="Выберите действие"
    )
