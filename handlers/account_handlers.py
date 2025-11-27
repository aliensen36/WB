# handlers/account_handlers.py
from aiogram import Router, F
from aiogram.types import Message
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession
from FSM.account_states import AddAccountStates, AccountManagementStates
from database.account_manager import AccountManager
from database.models import SellerAccount
from functions.wb_api import WBAPI
from keyboards.account_kb import get_main_accounts_keyboard, get_accounts_keyboard, \
    get_cancel_keyboard, get_account_management_keyboard, get_account_delete_confirm_keyboard
import logging
from datetime import datetime

from keyboards.main_kb import get_main_keyboard

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
# Работа c кабинетом
# ===========================================================================================


# @account_router.message(F.text.startswith("🔹"))
# async def select_account(message: Message, state: FSMContext, session: AsyncSession):
#     """Обработчик выбора кабинета из списка"""
#     account_name = message.text[2:].strip()  # Убираем эмодзи
#
#     account_manager = AccountManager(session)
#     all_accounts = await account_manager.get_all_accounts()
#
#     # Ищем кабинет по названию
#     selected_account = None
#     for account in all_accounts:
#         display_name = account.account_name or f"Кабинет {account.id}"
#         if display_name == account_name:
#             selected_account = account
#             break
#
#     if selected_account:
#         await state.update_data(selected_account_id=selected_account.id)
#         await state.set_state(AccountManagementStates.managing_account)
#
#         await show_account_details(message, selected_account, session)
#     else:
#         await message.answer("❌ Кабинет не найден")
#
#
# async def show_account_details(message: Message, account: SellerAccount, session: AsyncSession):
#     """Показать детали кабинета и меню действий"""
#     account_display_name = account.account_name or f"Кабинет {account.id}"
#
#     keyboard = get_account_management_keyboard()
#
#     await message.answer(
#         f"📁 <b>{account_display_name}</b>\n\n"
#         f"Выберите действие:",
#         reply_markup=keyboard
#     )
#
#
# @account_router.message(AccountManagementStates.managing_account, F.text == "📊 Статистика")
# async def show_account_stats(message: Message, state: FSMContext, session: AsyncSession):
#     """Показать статистику кабинета в требуемом формате"""
#     data = await state.get_data()
#     account_id = data.get('selected_account_id')
#
#     account_manager = AccountManager(session)
#     account = await account_manager.get_account_by_id(account_id)
#
#     if account:
#         account_display_name = account.account_name or f"Кабинет {account.id}"
#
#         # Показываем сообщение о загрузке
#         loading_msg = await message.answer(
#             f"📊 <b>Статистика: {account_display_name}</b>\n\n"
#             f"🔄 Получение данных...",
#             reply_markup=get_account_management_keyboard()
#         )
#
#         try:
#             # Получаем статистику через WB API
#             wb_api = WBAPI(account.api_key)
#             stats = await wb_api.get_today_stats_for_message()
#
#             # Получаем данные
#             orders_quantity = stats["orders"]["quantity"]
#             orders_amount = stats["orders"]["amount"]
#             sales_quantity = stats["sales"]["quantity"]
#             sales_amount = stats["sales"]["amount"]
#
#             # Форматируем суммы
#             formatted_orders_amount = f"{orders_amount:,.0f} ₽".replace(",", " ").replace(".", ",")
#             formatted_sales_amount = f"{sales_amount:,.2f} ₽".replace(",", " ").replace(".", ",")
#
#             # Получаем текущую дату
#             today = datetime.now().strftime("%d.%m.%Y")
#
#             # Формируем сообщение в требуемом формате
#             stats_text = f"📊 Статистика: <b>{account_display_name}</b>\n\n"
#             stats_text += f"📅 За сегодня (<b>{today}</b>)\n\n"
#             stats_text += f"🛒 <b>Заказы</b>\n\n"
#             stats_text += f"<b>{orders_quantity}</b> шт. на <b>{formatted_orders_amount}</b>\n\n"
#             stats_text += f"✔️ <b>Выкупы</b>\n\n"
#             stats_text += f"<b>{sales_quantity}</b> шт. на <b>{formatted_sales_amount}</b>"
#
#             # УДАЛЯЕМ сообщение о загрузке и отправляем новое с результатами
#             await loading_msg.delete()
#             await message.answer(
#                 stats_text,
#                 reply_markup=get_account_management_keyboard()
#             )
#
#         except ValueError as e:
#             error_message = str(e)
#             # УДАЛЯЕМ сообщение о загрузке и отправляем новое с ошибкой
#             await loading_msg.delete()
#             await message.answer(
#                 f"❌ <b>Ошибка при получении статистики:</b>\n"
#                 f"{error_message}\n\n"
#                 f"<i>Проверьте API ключ и попробуйте позже</i>",
#                 reply_markup=get_account_management_keyboard()
#             )
#
#         except Exception as e:
#             logger.error(f"Неожиданная ошибка при получении статистики: {e}")
#             # УДАЛЯЕМ сообщение о загрузке и отправляем новое с ошибкой
#             await loading_msg.delete()
#             await message.answer(
#                 f"❌ <b>Произошла непредвиденная ошибка</b>\n\n"
#                 f"<i>Попробуйте позже или проверьте настройки кабинета</i>",
#                 reply_markup=get_account_management_keyboard()
#             )
#
#     else:
#         await message.answer("❌ Кабинет не найден")
#
#
#
#
# @account_router.message(AccountManagementStates.managing_account, F.text == "✏️ Изменить")
# async def start_rename_account(message: Message, state: FSMContext):
#     """Начать процесс переименования кабинета"""
#     await state.set_state(AccountManagementStates.waiting_rename)
#     await message.answer(
#         "✏️ Введите новое название для кабинета:",
#         reply_markup=get_cancel_keyboard()
#     )
#
#
# @account_router.message(AccountManagementStates.waiting_rename)
# async def process_rename_account(message: Message, state: FSMContext, session: AsyncSession):
#     """Обработка нового названия кабинета"""
#     if message.text == "❌ Отмена":
#         await state.set_state(AccountManagementStates.managing_account)
#         await message.answer(
#             "❌ Переименование отменено.",
#             reply_markup=get_account_management_keyboard()
#         )
#         return
#
#     new_name = message.text.strip()
#
#     if len(new_name) > 100:
#         await message.answer(
#             "❌ Слишком длинное название. Максимум 100 символов.\n"
#             "Введите другое название:"
#         )
#         return
#
#     data = await state.get_data()
#     account_id = data.get('selected_account_id')
#
#     account_manager = AccountManager(session)
#     updated_account = await account_manager.update_account_name(account_id, new_name)
#
#     if updated_account:
#         await state.set_state(AccountManagementStates.managing_account)
#         await message.answer(
#             f"✅ Кабинет переименован в: <b>{new_name}</b>",
#             reply_markup=get_account_management_keyboard()
#         )
#     else:
#         await message.answer(
#             "❌ Ошибка при переименовании кабинета.",
#             reply_markup=get_account_management_keyboard()
#         )


@account_router.message(AccountManagementStates.managing_account, F.text == "🗑 Удалить")
async def start_delete_account(message: Message, state: FSMContext):
    """Начать процесс удаления кабинета"""
    await state.set_state(AccountManagementStates.waiting_delete_confirm)
    await message.answer(
        "🗑 Вы уверены, что хотите удалить этот кабинет?\n\n"
        "Эта операция необратима!",
        reply_markup=get_account_delete_confirm_keyboard()
    )


@account_router.message(AccountManagementStates.waiting_delete_confirm, F.text == "✅ Да, удалить")
async def confirm_delete_account(message: Message, state: FSMContext, session: AsyncSession):
    """Подтверждение удаления кабинета"""
    data = await state.get_data()
    account_id = data.get('selected_account_id')

    account_manager = AccountManager(session)
    account = await account_manager.get_account_by_id(account_id)

    if account:
        account_display_name = account.account_name or f"Кабинет {account.id}"
        success = await account_manager.delete_account(account_id)

        if success:
            await state.clear()
            # Получаем обновленный список кабинетов
            all_accounts = await account_manager.get_all_accounts()

            if all_accounts:
                await message.answer(
                    f"✅ Кабинет <b>{account_display_name}</b> удален.",
                    reply_markup=get_accounts_keyboard(all_accounts)
                )
            else:
                await message.answer(
                    f"✅ Кабинет <b>{account_display_name}</b> удален.",
                    reply_markup=get_main_accounts_keyboard()
                )
        else:
            await state.set_state(AccountManagementStates.managing_account)
            await message.answer(
                "❌ Ошибка при удалении кабинета.",
                reply_markup=get_account_management_keyboard()
            )
    else:
        await state.clear()
        await message.answer(
            "❌ Кабинет не найден.",
            reply_markup=get_main_accounts_keyboard()
        )


@account_router.message(AccountManagementStates.waiting_delete_confirm, F.text == "❌ Отмена удаления")
async def cancel_delete_account(message: Message, state: FSMContext):
    """Отмена удаления кабинета"""
    await state.set_state(AccountManagementStates.managing_account)
    await message.answer(
        "❌ Удаление отменено.",
        reply_markup=get_account_management_keyboard()
    )


@account_router.message(AccountManagementStates.managing_account, F.text == "⬅️ Назад")
async def back_to_accounts_list(message: Message, state: FSMContext, session: AsyncSession):
    """Возврат к списку кабинетов"""
    await state.clear()

    account_manager = AccountManager(session)
    all_accounts = await account_manager.get_all_accounts()

    if all_accounts:
        await message.answer(
            "📋 Список кабинетов:",
            reply_markup=get_accounts_keyboard(all_accounts)
        )
    else:
        await message.answer(
            "📋 Пока нет добавленных кабинетов",
            reply_markup=get_main_accounts_keyboard()
        )
