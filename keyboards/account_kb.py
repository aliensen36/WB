# keyboards/account_kb.py
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import ReplyKeyboardBuilder, InlineKeyboardBuilder
from database.models import SellerAccount
from typing import List


# ===========================================================================================
# Кабинеты и добавление нового
# ===========================================================================================


def get_accounts_keyboard(accounts: List[SellerAccount]) -> ReplyKeyboardMarkup:
    """Клавиатура с существующими кабинетами и кнопкой добавления"""
    builder = ReplyKeyboardBuilder()

    # Кнопки для существующих кабинетов
    for account in accounts:
        account_name = account.account_name or f"Кабинет {account.id}"
        builder.add(KeyboardButton(text=f"🔹 {account_name}"))

    # Кнопка добавления нового кабинета
    builder.add(KeyboardButton(text="➕ Добавить кабинет"))

    builder.adjust(2)
    return builder.as_markup(resize_keyboard=True)


def get_main_accounts_keyboard() -> ReplyKeyboardMarkup:
    """Главная клавиатура управления кабинетами"""
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="➕ Добавить кабинет")],
        ],
        resize_keyboard=True
    )


def get_cancel_keyboard() -> ReplyKeyboardMarkup:
    """Клавиатура для отмены операции"""
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="❌ Отмена")]],
        resize_keyboard=True
    )



# ===========================================================================================
# Управление кабинетом
# ===========================================================================================


def get_account_management_keyboard() -> ReplyKeyboardMarkup:
    """Реплайн-клавиатура для действий с кабинетом"""
    builder = ReplyKeyboardBuilder()

    builder.add(
        KeyboardButton(text="📊 Статистика"),
        KeyboardButton(text="✏️ Изменить"),
        KeyboardButton(text="🗑 Удалить"),
        KeyboardButton(text="⬅️ Назад")
    )

    builder.adjust(2)  # 2 кнопки в каждом ряду
    return builder.as_markup(resize_keyboard=True)


def get_account_delete_confirm_keyboard() -> ReplyKeyboardMarkup:
    """Реплайн-клавиатура подтверждения удаления кабинета"""
    builder = ReplyKeyboardBuilder()

    builder.add(
        KeyboardButton(text="✅ Да, удалить"),
        KeyboardButton(text="❌ Отмена удаления")
    )

    builder.adjust(2)  # 2 кнопки в ряду
    return builder.as_markup(resize_keyboard=True)
