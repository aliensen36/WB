# accounts_settings_handlers.py
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession
from aiogram.utils.keyboard import InlineKeyboardBuilder
from FSM.account_states import AccountManagementStates, AddAccountStates
from database.account_manager import AccountManager
from keyboards.account_kb import get_shops_management_keyboard, get_cancel_inline_keyboard
from keyboards.settings_kb import (
    get_settings_keyboard,
)
import logging

logger = logging.getLogger(__name__)

accounts_settings_router = Router()


@accounts_settings_router.callback_query(F.data == "manage_shops")
async def manage_shops(callback: CallbackQuery, session: AsyncSession):
    """Переход к управлению магазинами"""
    account_manager = AccountManager(session)
    all_accounts = await account_manager.get_all_accounts()

    shops_text = "🏪 <b>Управление магазинами</b>\n\n"

    if all_accounts:
        shops_text += f"📋 <b>Ваши магазины:</b>\n"
        for i, account in enumerate(all_accounts, 1):
            account_name = account.account_name or f"Магазин {account.id}"
            shops_text += f"{i}. {account_name}\n"
    else:
        shops_text += "📭 <i>У вас пока нет добавленных магазинов</i>\n"

    shops_text += "\nВыберите действие:"

    await callback.message.edit_text(
        shops_text,
        reply_markup=get_shops_management_keyboard()
    )


@accounts_settings_router.callback_query(F.data == "add_shop")
async def add_shop_callback(callback: CallbackQuery, state: FSMContext):
    """Обработчик кнопки добавления магазина"""
    await callback.message.delete()

    # Создаем клавиатуру с кнопкой отмены
    cancel_kb = get_cancel_inline_keyboard()

    await callback.message.answer(
        "🔐 <b>Добавление нового магазина</b>\n\n"
        "Пожалуйста, введите ваш API ключ от Wildberries:\n\n"
        "<i>Как получить API ключ:</i>\n"
        "1. Зайдите в личный кабинет продавца WB\n"
        "2. Настройки → Доступ к API\n"
        "3. Сгенерируйте новый ключ или используйте существующий "
        "с доступами к категориям «Аналитика» и «Статистика», уровень: «Только чтение».\n\n"
        "<i>Или нажмите \"❌ Отмена\" для выхода</i>",
        reply_markup=cancel_kb
    )
    await state.set_state(AddAccountStates.waiting_for_api_key)


@accounts_settings_router.callback_query(F.data == "cancel_operation")
async def handle_inline_cancel(callback: CallbackQuery, state: FSMContext):
    """Обработчик инлайн-кнопки отмены"""
    await state.clear()
    await callback.message.edit_text(
        "❌ Операция отменена.",
        reply_markup=get_settings_keyboard()
    )


@accounts_settings_router.message(F.text == "❌ Отмена")
async def handle_cancel(message: Message, state: FSMContext):
    """Универсальный обработчик отмены"""
    await state.clear()

    await message.answer(
        "❌ Операция отменена.",
        reply_markup=get_settings_keyboard()
    )


@accounts_settings_router.message(AddAccountStates.waiting_for_api_key)
async def process_api_key(message: Message, state: FSMContext, session: AsyncSession):
    """Обработка введенного API ключа"""
    if message.text == "❌ Отмена":
        await handle_cancel(message, state)
        return

    api_key = message.text.strip()

    # Простая валидация API ключа
    if len(api_key) < 10:
        cancel_kb = get_cancel_inline_keyboard()
        await message.answer(
            "❌ <b>Некорректный API ключ</b>\n\n"
            "API ключ должен содержать не менее 10 символов.\n"
            "Пожалуйста, введите корректный API ключ:\n\n"
            "<i>Или нажмите \"❌ Отмена\" для выхода</i>",
            reply_markup=cancel_kb
        )
        return

    await state.update_data(api_key=api_key)

    cancel_kb = get_cancel_inline_keyboard()
    await message.answer(
        "📝 <b>Теперь введите название для этого магазина (необязательно):</b>\n\n"
        "Например: \"Основной магазин\", \"Тестовый аккаунт\"\n"
        "Или отправьте \"-\" чтобы пропустить\n\n"
        "<i>Или нажмите \"❌ Отмена\" для выхода</i>",
        reply_markup=cancel_kb
    )
    await state.set_state(AddAccountStates.waiting_for_account_name)


@accounts_settings_router.message(AddAccountStates.waiting_for_account_name)
async def process_account_name(message: Message, state: FSMContext, session: AsyncSession):
    """Обработка названия магазина и сохранение"""
    if message.text == "❌ Отмена":
        await handle_cancel(message, state)
        return

    account_name = message.text.strip()

    # Обработка пропуска названия
    if account_name == "-" or account_name.lower() == "пропустить":
        account_name = None
    elif len(account_name) > 100:
        cancel_kb = get_cancel_inline_keyboard()
        await message.answer(
            "❌ <b>Слишком длинное название</b>\n\n"
            "Название не должно превышать 100 символов.\n"
            "Пожалуйста, введите более короткое название:\n\n"
            "<i>Или нажмите \"❌ Отмена\" для выхода</i>",
            reply_markup=cancel_kb
        )
        return

    # Получаем данные из состояния
    data = await state.get_data()
    api_key = data.get('api_key')

    # Создаем магазин
    account_manager = AccountManager(session)
    try:
        account = await account_manager.create_account(
            api_key=api_key,
            account_name=account_name
        )

        display_name = account.account_name or "Без названия"

        await message.answer(
            f"✅ <b>Магазин успешно добавлен!</b>\n\n"
            f"Теперь вы можете работать с ним.\n"
            f"Название: <b>{display_name}</b>",
            reply_markup=get_settings_keyboard()
        )

    except ValueError as e:
        error_message = str(e)
        if "уже используется" in error_message:
            cancel_kb = get_cancel_inline_keyboard()
            await message.answer(
                "❌ <b>Этот API ключ уже используется</b>\n\n"
                "Данный API ключ уже привязан к другому кабинету.\n"
                "Пожалуйста, введите другой API ключ:\n\n"
                "<i>Или нажмите \"❌ Отмена\" для выхода</i>",
                reply_markup=cancel_kb
            )
            # Возвращаем в состояние ожидания API ключа
            await state.set_state(AddAccountStates.waiting_for_api_key)
        else:
            await message.answer(
                f"❌ <b>Ошибка при добавлении магазина:</b>\n{error_message}",
                reply_markup=get_settings_keyboard()
            )

    except Exception as e:
        logger.error(f"Неожиданная ошибка при создании магазина: {e}")
        await message.answer(
            "❌ <b>Произошла непредвиденная ошибка</b>\n\n"
            "Попробуйте добавить магазин позже.",
            reply_markup=get_settings_keyboard()
        )

    finally:
        await state.clear()


@accounts_settings_router.callback_query(F.data == "edit_shop")
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

    builder = InlineKeyboardBuilder()
    for account in all_accounts:
        account_name = account.account_name or f"Магазин {account.id}"
        builder.add(InlineKeyboardButton(
            text=f" {account_name}",
            callback_data=f"edit_account_{account.id}"
        ))
    builder.add(InlineKeyboardButton(text="⬅️ Назад", callback_data="manage_shops"))
    builder.adjust(1)

    await callback.message.edit_text(
        "Выберите магазин для изменения названия:",
        reply_markup=builder.as_markup()
    )


@accounts_settings_router.callback_query(F.data.startswith("edit_account_"))
async def start_edit_account_name(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Начало процесса изменения названия магазина"""
    account_id = int(callback.data.split("_")[2])

    account_manager = AccountManager(session)
    account = await account_manager.get_account_by_id(account_id)

    if not account:
        await callback.answer("❌ Магазин не найден")
        return

    # Сохраняем ID магазина в состоянии
    await state.update_data(account_id=account_id)
    await state.set_state(AccountManagementStates.waiting_rename)

    current_name = account.account_name or f"Магазин {account.id}"

    builder = InlineKeyboardBuilder()
    builder.add(InlineKeyboardButton(text="⬅️ Отмена", callback_data="manage_shops"))

    await callback.message.edit_text(
        f"✏️ <b>Изменение названия магазина</b>\n\n"
        f"Текущее название: <b>{current_name}</b>\n\n"
        f"<b>Введите новое название магазина:</b>\n"
        f"<i>Или нажмите 'Отмена' для возврата</i>",
        reply_markup=builder.as_markup(),
        parse_mode="HTML"
    )


@accounts_settings_router.message(AccountManagementStates.waiting_rename)
async def process_new_account_name(message: Message, state: FSMContext, session: AsyncSession):
    """Обработка нового названия магазина"""
    if message.text == "❌ Отмена":
        await handle_cancel(message, state)
        return

    new_name = message.text.strip()

    if len(new_name) < 2:
        await message.answer(
            "❌ <b>Слишком короткое название</b>\n\n"
            "Название магазина должно содержать хотя бы 2 символа.\n"
            "Пожалуйста, введите новое название:"
        )
        return

    if len(new_name) > 100:
        await message.answer(
            "❌ <b>Слишком длинное название</b>\n\n"
            "Название магазина не должно превышать 100 символов.\n"
            "Пожалуйста, введите более короткое название:"
        )
        return

    # Получаем данные из состояния
    data = await state.get_data()
    account_id = data.get("account_id")

    if not account_id:
        await message.answer(
            "❌ <b>Ошибка данных</b>\n\n"
            "Не удалось определить магазин для редактирования."
        )
        await state.clear()
        return

    account_manager = AccountManager(session)
    updated_account = await account_manager.update_account_name(account_id, new_name)

    if updated_account:
        builder = InlineKeyboardBuilder()
        builder.add(InlineKeyboardButton(text="🏪 К управлению магазинами", callback_data="manage_shops"))

        await message.answer(
            f"✅ <b>Название изменено</b>\n\n"
            f"Магазин успешно переименован в:\n"
            f"<b>«{new_name}»</b>",
            reply_markup=builder.as_markup()
        )
    else:
        await message.answer(
            "❌ <b>Ошибка изменения</b>\n\n"
            "Не удалось изменить название магазина.\n"
            "Возможно, магазин был удален.",
            reply_markup=get_settings_keyboard()
        )

    # Очищаем состояние
    await state.clear()


@accounts_settings_router.callback_query(F.data == "delete_shop")
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
        "Выберите магазин для удаления:",
        reply_markup=builder.as_markup()
    )


@accounts_settings_router.callback_query(F.data.startswith("delete_account_"))
async def confirm_delete_account(callback: CallbackQuery, session: AsyncSession):
    """Подтверждение удаления магазина"""
    account_id = int(callback.data.split("_")[2])

    account_manager = AccountManager(session)
    account = await account_manager.get_account_by_id(account_id)

    if not account:
        await callback.answer("❌ Магазин не найден")
        return

    account_name = account.account_name or f"Магазин {account.id}"

    builder = InlineKeyboardBuilder()
    builder.add(
        InlineKeyboardButton(text="✅ Да, удалить", callback_data=f"confirm_delete_{account_id}"),
        InlineKeyboardButton(text="❌ Нет, отменить", callback_data="delete_shop")
    )
    builder.adjust(2)

    await callback.message.edit_text(
        f"🗑 <b>Подтвердите удаление</b>\n\n"
        f"Вы действительно хотите удалить магазин:\n"
        f"<b>{account_name}</b>\n\n"
        f"<i>Это действие нельзя отменить!</i>",
        reply_markup=builder.as_markup()
    )


@accounts_settings_router.callback_query(F.data.startswith("confirm_delete_"))
async def execute_delete_account(callback: CallbackQuery, session: AsyncSession):
    """Выполнение удаления магазина"""
    account_id = int(callback.data.split("_")[2])

    account_manager = AccountManager(session)
    account = await account_manager.get_account_by_id(account_id)

    if not account:
        await callback.answer("❌ Магазин не найден")
        return

    account_name = account.account_name or f"Магазин {account.id}"

    # Удаляем магазин
    success = await account_manager.delete_account(account_id)

    if success:
        # Получаем обновленный список магазинов
        all_accounts = await account_manager.get_all_accounts()

        if all_accounts:
            shops_text = "🏪 <b>Управление магазинами</b>\n\n"
            shops_text += f"✅ <b>Магазин \"{account_name}\" успешно удален!</b>\n\n"
            shops_text += f"📋 <b>Ваши магазины:</b>\n"

            for i, acc in enumerate(all_accounts, 1):
                acc_name = acc.account_name or f"Магазин {acc.id}"
                shops_text += f"{i}. {acc_name}\n"

            shops_text += "\nВыберите действие:"

            await callback.message.edit_text(
                shops_text,
                reply_markup=get_shops_management_keyboard()
            )
        else:
            await callback.message.edit_text(
                f"✅ <b>Магазин \"{account_name}\" успешно удален!</b>\n\n"
                f"📭 <i>Больше нет добавленных магазинов</i>",
                reply_markup=get_shops_management_keyboard()
            )
    else:
        await callback.message.edit_text(
            f"❌ <b>Ошибка при удалении магазина</b>\n\n"
            f"Не удалось удалить магазин <b>{account_name}</b>.\n"
            f"Попробуйте позже.",
            reply_markup=get_shops_management_keyboard()
        )


@accounts_settings_router.callback_query(F.data == "back_to_settings")
async def back_to_settings(callback: CallbackQuery, session: AsyncSession):
    """Возврат к главному меню настроек"""
    await show_settings(callback, session)


async def show_settings(callback_or_message: CallbackQuery | Message, session: AsyncSession):
    """Показать главное меню настроек"""
    account_manager = AccountManager(session)
    all_accounts = await account_manager.get_all_accounts()

    settings_text = f"⚙️ <b>Настройки магазинов</b>\n\n"

    if all_accounts:
        settings_text += f"📋 <b>Список магазинов:</b>\n"
        for i, account in enumerate(all_accounts, 1):
            account_name = account.account_name or f"Магазин {account.id}"
            settings_text += f"{i}. <b>{account_name}</b>\n"
        settings_text += f"\n"
    else:
        settings_text += f"📋 <b>Список магазинов:</b>\n"
        settings_text += f"   <i>пока нет магазинов</i>\n\n"

    settings_text += f"<b>Выберите раздел для управления:</b>"

    if isinstance(callback_or_message, CallbackQuery):
        await callback_or_message.message.edit_text(
            settings_text,
            reply_markup=get_settings_keyboard()
        )
    else:
        await callback_or_message.answer(
            settings_text,
            reply_markup=get_settings_keyboard()
        )