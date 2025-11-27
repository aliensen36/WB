# Клавиатура главного меню
from aiogram.types import KeyboardButton
from aiogram.utils.keyboard import ReplyKeyboardBuilder


# def get_main_keyboard():
#     keyboard = ReplyKeyboardBuilder()
#     keyboard.add(KeyboardButton(text="📊 Статистика за сегодня"))
#     keyboard.add(KeyboardButton(text="📈 Статистика за вчера"))
#     keyboard.add(KeyboardButton(text="🕐 Статистика за 24 часа"))
#     keyboard.add(KeyboardButton(text="📅 Выбрать период"))
#     keyboard.add(KeyboardButton(text="🚚 Поставки"))
#     keyboard.add(KeyboardButton(text="📦 Остатки"))
#     keyboard.adjust(2)
#     return keyboard.as_markup(resize_keyboard=True)

# Клавиатура выбора периода
def get_period_keyboard():
    keyboard = ReplyKeyboardBuilder()
    keyboard.add(KeyboardButton(text="Сегодня"))
    keyboard.add(KeyboardButton(text="Вчера"))
    keyboard.add(KeyboardButton(text="3 дня"))
    keyboard.add(KeyboardButton(text="7 дней"))
    keyboard.add(KeyboardButton(text="30 дней"))
    keyboard.add(KeyboardButton(text="↩️ Назад"))
    keyboard.adjust(2)
    return keyboard.as_markup(resize_keyboard=True)
