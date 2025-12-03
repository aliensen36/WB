# handlers/account_handlers.py
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession
from FSM.account_states import AddAccountStates, AccountManagementStates
from database.account_manager import AccountManager
from functions.wb_api import WBAPI
from keyboards.account_kb import get_main_accounts_keyboard, get_accounts_keyboard, \
    get_cancel_keyboard, get_account_management_keyboard, get_account_delete_confirm_keyboard
import logging
from datetime import datetime

from keyboards.main_kb import get_main_keyboard
from keyboards.settings_kb import get_shops_management_keyboard

# Настройка логирования
logger = logging.getLogger(__name__)

account_router = Router()


# ===========================================================================================
# Обработчик отмены
# ===========================================================================================


@account_router.message(F.text == "❌ Отмена")
async def handle_cancel(message: Message, state: FSMContext):
    """Универсальный обработчик отмены с возвратом к главному меню"""
    # Очищаем состояние
    await state.clear()

    # Возвращаем к главному меню
    await message.answer(
        "❌ Операция отменена.",
        reply_markup=get_main_keyboard()
    )


# ===========================================================================================
# Создание кабинета
# ===========================================================================================


@account_router.message(F.text == "➕ Добавить кабинет")
async def start_add_account(message: Message, state: FSMContext):
    """Начало процесса добавления кабинета"""
    await message.answer(
        "🔐 Добавление нового кабинета\n\n"
        "Пожалуйста, введите ваш API ключ от Wildberries:\n\n"
        "Как получить API ключ:\n"
        "1. Зайдите в личный кабинет продавца WB\n"
        "2. Настройки → Доступ к API\n"
        "3. Сгенерируйте новый ключ или используйте существующий "
        "с доступами к категориям «Аналитика» и «Статистика», уровень: «Только чтение».\n\n"
        "<i>Или нажмите \"❌ Отмена\" для выхода</i>",
        reply_markup=get_cancel_keyboard()
    )
    await state.set_state(AddAccountStates.waiting_for_api_key)


@account_router.message(AddAccountStates.waiting_for_api_key)
async def process_api_key(message: Message, state: FSMContext, session: AsyncSession):
    """Обработка введенного API ключа"""
    if message.text == "❌ Отмена":
        return

    api_key = message.text.strip()

    # Простая валидация API ключа
    if len(api_key) < 10:
        await message.answer(
            "❌ Некорректный API ключ\n\n"
            "API ключ должен содержать не менее 10 символов.\n"
            "Пожалуйста, введите корректный API ключ:\n\n"
            "<i>Или нажмите \"❌ Отмена\" для выхода</i>",
            reply_markup=get_cancel_keyboard()
        )
        return

    await state.update_data(api_key=api_key)

    await message.answer(
        "📝 Теперь введите название для этого кабинета (необязательно):\n\n"
        "Например: \"Основной магазин\", \"Тестовый аккаунт\"\n"
        "Или отправьте \"-\" чтобы пропустить\n\n"
        "<i>Или нажмите \"❌ Отмена\" для выхода</i>",
        reply_markup=get_cancel_keyboard()  # Кнопка отмены на втором шаге
    )
    await state.set_state(AddAccountStates.waiting_for_account_name)


@account_router.message(AddAccountStates.waiting_for_account_name)
async def process_account_name(message: Message, state: FSMContext, session: AsyncSession):
    """Обработка названия кабинета и сохранение"""
    if message.text == "❌ Отмена":
        return

    account_name = message.text.strip()

    # Обработка пропуска названия
    if account_name == "-" or account_name.lower() == "пропустить":
        account_name = None
    elif len(account_name) > 100:
        await message.answer(
            "❌ Слишком длинное название\n\n"
            "Название не должно превышать 100 символов.\n"
            "Пожалуйста, введите более короткое название:\n\n"
            "<i>Или нажмите \"❌ Отмена\" для выхода</i>",
            reply_markup=get_cancel_keyboard()  # Кнопка отмены при ошибке
        )
        return

    # Получаем данные из состояния
    data = await state.get_data()
    api_key = data.get('api_key')

    # Создаем кабинет
    account_manager = AccountManager(session)
    try:
        account = await account_manager.create_account(
            api_key=api_key,
            account_name=account_name
        )

        # Получаем обновленный список кабинетов для клавиатуры
        all_accounts = await account_manager.get_all_accounts()

        await message.answer(
            f"✅ Кабинет успешно добавлен!\n\n"
            f"Теперь вы можете работать с ним.",
            reply_markup=get_main_keyboard()
        )

    except ValueError as e:
        error_message = str(e)
        if "уже используется" in error_message:
            await message.answer(
                "❌ Этот API ключ уже используется\n\n"
                "Данный API ключ уже привязан к другому кабинету.\n"
                "Пожалуйста, введите другой API ключ:\n\n"
                "<i>Или нажмите \"❌ Отмена\" для выхода</i>",
                reply_markup=get_cancel_keyboard()  # Кнопка отмены при ошибке
            )
            # Возвращаем в состояние ожидания API ключа
            await state.set_state(AddAccountStates.waiting_for_api_key)
        else:
            await message.answer(
                f"❌ Ошибка при добавлении кабинета:\n{error_message}",
                reply_markup=get_main_accounts_keyboard()
            )

    except Exception as e:
        print(f"💥 Неожиданная ошибка при создании кабинета: {e}")
        await message.answer(
            "❌ Произошла непредвиденная ошибка\n\n"
            "Попробуйте добавить кабинет позже.",
            reply_markup=get_main_accounts_keyboard()
        )

    finally:
        await state.clear()


# ===========================================================================================
# Управление кабинетами
# ===========================================================================================


@account_router.callback_query(F.data == "delete_shop")
async def delete_shop_callback(callback: CallbackQuery, session: AsyncSession):
    """Обработчик кнопки удаления магазина"""
    account_manager = AccountManager(session)
    all_accounts = await account_manager.get_all_accounts()

    if not all_accounts:
        await callback.message.edit_text(
            "<b>Нет магазинов для удаления</b>",
            reply_markup=get_shops_management_keyboard()
        )
        return

    from aiogram.utils.keyboard import InlineKeyboardBuilder

    builder = InlineKeyboardBuilder()
    for account in all_accounts:
        account_name = account.account_name or f"Магазин {account.id}"
        builder.add(InlineKeyboardButton(
            text=f"🗑 {account_name}",
            callback_data=f"delete_account_{account.id}"
        ))
    builder.add(InlineKeyboardButton(text="⬅️ Назад", callback_data="manage_shops"))
    builder.adjust(1)

    await callback.message.edit_text(
        "<b>Выберите магазин для удаления:</b>",
        reply_markup=builder.as_markup()
    )


@account_router.callback_query(F.data == "edit_shop")
async def edit_shop_callback(callback: CallbackQuery, session: AsyncSession):
    """Обработчик кнопки изменения названия магазина"""
    account_manager = AccountManager(session)
    all_accounts = await account_manager.get_all_accounts()

    if not all_accounts:
        await callback.message.edit_text(
            "<b>Нет магазинов для редактирования</b>",
            reply_markup=get_shops_management_keyboard()
        )
        return

    from aiogram.utils.keyboard import InlineKeyboardBuilder

    builder = InlineKeyboardBuilder()
    for account in all_accounts:
        account_name = account.account_name or f"Магазин {account.id}"
        builder.add(InlineKeyboardButton(
            text=f"✏️ {account_name}",
            callback_data=f"edit_account_{account.id}"
        ))
    builder.add(InlineKeyboardButton(text="⬅️ Назад", callback_data="manage_shops"))
    builder.adjust(1)

    await callback.message.edit_text(
        "<b>Выберите магазин для изменения названия:</b>",
        reply_markup=builder.as_markup()
    )


