# settings_handlers.py
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession

from FSM.account_states import AccountManagementStates
from database.account_manager import AccountManager
from handlers.account_handlers import start_add_account, process_api_key, process_account_name
import logging

from keyboards.main_kb import get_main_keyboard
from keyboards.settings_kb import get_settings_keyboard

logger = logging.getLogger(__name__)

settings_router = Router()


@settings_router.message(F.text == "⚙️ Настройки")
async def show_settings(message: Message, session: AsyncSession):
    """Показать настройки с инлайн-кнопками и списком магазинов"""
    account_manager = AccountManager(session)
    all_accounts = await account_manager.get_all_accounts()

    accounts_count = len(all_accounts) if all_accounts else 0

    settings_text = f"⚙️ <b>Настройки магазинов</b>\n\n"

    if all_accounts:
        settings_text += f"📋 <b>Добавленные магазины:</b>\n"
        for i, account in enumerate(all_accounts, 1):
            account_name = account.account_name or f"Магазин {account.id}"
            settings_text += f"{i}. <b>{account_name}</b>\n"
        settings_text += f"\n"
    else:
        settings_text += f"📋 <b>Добавленные магазины:</b>\n"
        settings_text += f"   <i>пока нет магазинов</i>\n\n"

    settings_text += f"<b>Доступные действия:</b>\n"
    settings_text += f"• Добавить новый магазин\n"
    settings_text += f"• Удалить существующий магазин\n\n"
    settings_text += f"Выберите действие:"

    await message.answer(
        settings_text,
        reply_markup=get_settings_keyboard()
    )


@settings_router.callback_query(F.data == "add_shop")
async def add_shop_callback(callback: CallbackQuery, state: FSMContext):
    """Обработчик кнопки добавления магазина"""
    await callback.message.delete()
    await start_add_account(callback.message, state)


@settings_router.callback_query(F.data == "delete_shop")
async def delete_shop_callback(callback: CallbackQuery, session: AsyncSession):
    """Обработчик кнопки удаления магазина"""
    account_manager = AccountManager(session)
    all_accounts = await account_manager.get_all_accounts()

    if not all_accounts:
        await callback.message.edit_text(
            "<b>Нет магазинов для удаления</b>",
            reply_markup=get_settings_keyboard()
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
    builder.add(InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_settings"))
    builder.adjust(1)

    await callback.message.edit_text(
        "<b>Выберите магазин для удаления:</b>",
        reply_markup=builder.as_markup()
    )


@settings_router.callback_query(F.data.startswith("delete_account_"))
async def confirm_delete_account(callback: CallbackQuery, session: AsyncSession):
    """Подтверждение удаления магазина"""
    account_id = int(callback.data.split("_")[2])

    account_manager = AccountManager(session)
    account = await account_manager.get_account_by_id(account_id)

    if not account:
        await callback.answer("❌ Магазин не найден")
        return

    account_name = account.account_name or f"Магазин {account.id}"

    from aiogram.utils.keyboard import InlineKeyboardBuilder

    builder = InlineKeyboardBuilder()
    builder.add(
        InlineKeyboardButton(text="✅ Да, удалить", callback_data=f"confirm_delete_{account_id}"),
        InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_delete")
    )
    builder.adjust(2)

    await callback.message.edit_text(
        f"🗑 <b>Подтвердите удаление</b>\n\n"
        f"Вы действительно хотите удалить магазин:\n"
        f"<b>{account_name}</b>\n\n"
        f"<i>Это действие нельзя отменить!</i>",
        reply_markup=builder.as_markup()
    )


@settings_router.callback_query(F.data == "cancel_delete")
async def cancel_delete(callback: CallbackQuery, session: AsyncSession):
    """Отмена удаления и возврат к списку магазинов для удаления"""
    await delete_shop_callback(callback, session)


@settings_router.callback_query(F.data.startswith("confirm_delete_"))
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
            # Возвращаем к настройкам с обновленным списком
            settings_text = f"⚙️ <b>Настройки магазинов</b>\n\n"
            settings_text += f"✅ <b>Магазин \"{account_name}\" успешно удален!</b>\n\n"
            settings_text += f"📋 <b>Добавленные магазины:</b>\n"

            for i, acc in enumerate(all_accounts, 1):
                acc_name = acc.account_name or f"Магазин {acc.id}"
                settings_text += f"{i}. <b>{acc_name}</b>\n"

            settings_text += f"\n<b>Доступные действия:</b>\n"
            settings_text += f"• Добавить новый магазин\n"
            settings_text += f"• Удалить существующий магазин\n\n"
            settings_text += f"Выберите действие:"

            await callback.message.edit_text(
                settings_text,
                reply_markup=get_settings_keyboard()
            )
        else:
            # Если магазинов не осталось, возвращаем к главному меню
            await callback.message.edit_text(
                f"✅ <b>Магазин \"{account_name}\" успешно удален!</b>\n\n"
                f"📭 <i>Больше нет добавленных магазинов</i>",
                reply_markup=get_main_keyboard()
            )
    else:
        await callback.message.edit_text(
            f"❌ <b>Ошибка при удалении магазина</b>\n\n"
            f"Не удалось удалить магазин <b>{account_name}</b>.\n"
            f"Попробуйте позже.",
            reply_markup=get_settings_keyboard()
        )


@settings_router.callback_query(F.data == "back_to_settings")
async def back_to_settings(callback: CallbackQuery, session: AsyncSession):
    """Возврат к настройкам - редактируем текущее сообщение"""
    account_manager = AccountManager(session)
    all_accounts = await account_manager.get_all_accounts()

    settings_text = f"⚙️ <b>Настройки магазинов</b>\n\n"

    if all_accounts:
        settings_text += f"📋 <b>Добавленные магазины:</b>\n"
        for i, account in enumerate(all_accounts, 1):
            account_name = account.account_name or f"Магазин {account.id}"
            settings_text += f"{i}. <b>{account_name}</b>\n"
        settings_text += f"\n"
    else:
        settings_text += f"📋 <b>Добавленные магазины:</b>\n"
        settings_text += f"   <i>пока нет магазинов</i>\n\n"

    settings_text += f"<b>Доступные действия:</b>\n"
    settings_text += f"• Добавить новый магазин\n"
    settings_text += f"• Удалить существующий магазин\n\n"
    settings_text += f"Выберите действие:"

    await callback.message.edit_text(
        settings_text,
        reply_markup=get_settings_keyboard()
    )


@settings_router.callback_query(F.data == "edit_shop")
async def edit_shop_callback(callback: CallbackQuery, session: AsyncSession):
    """Обработчик кнопки изменения названия магазина"""
    account_manager = AccountManager(session)
    all_accounts = await account_manager.get_all_accounts()

    if not all_accounts:
        await callback.message.edit_text(
            "<b>Нет магазинов для редактирования</b>",
            reply_markup=get_settings_keyboard()
        )
        return

    from aiogram.utils.keyboard import InlineKeyboardBuilder

    builder = InlineKeyboardBuilder()
    for account in all_accounts:
        account_name = account.account_name or f"Магазин {account.id}"
        builder.add(InlineKeyboardButton(
            text=f"{account_name}",
            callback_data=f"edit_account_{account.id}"
        ))
    builder.add(InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_settings"))
    builder.adjust(1)

    await callback.message.edit_text(
        "<b>Выберите магазин для изменения названия:</b>",
        reply_markup=builder.as_markup()
    )


@settings_router.callback_query(F.data.startswith("edit_account_"))
async def start_edit_account(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Запрос нового названия для магазина"""
    account_id = int(callback.data.split("_")[2])

    account_manager = AccountManager(session)
    account = await account_manager.get_account_by_id(account_id)

    if not account:
        await callback.answer("❌ Магазин не найден")
        return

    current_name = account.account_name or f"Магазин {account.id}"

    # Сохраняем ID магазина в состоянии FSM
    await state.update_data(editing_account_id=account_id)
    await state.set_state(AccountManagementStates.waiting_rename)

    from aiogram.utils.keyboard import InlineKeyboardBuilder

    builder = InlineKeyboardBuilder()
    builder.add(InlineKeyboardButton(
        text="❌ Отмена",
        callback_data=f"cancel_edit_{account_id}"
    ))

    await callback.message.edit_text(
        f"✏️ <b>Редактирование названия магазина</b>\n\n"
        f"Текущее название: <b>{current_name}</b>\n\n"
        f"Введите новое название для магазина:",
        reply_markup=builder.as_markup()
    )



@settings_router.callback_query(F.data.startswith("cancel_edit_"))
async def cancel_edit(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Отмена редактирования и возврат к списку магазинов"""
    await state.clear()  # Очищаем состояние
    await edit_shop_callback(callback, session)


@settings_router.message(AccountManagementStates.waiting_rename)
async def process_new_account_name(message: Message, state: FSMContext, session: AsyncSession):
    """Обработка нового названия магазина с использованием FSM"""
    new_name = message.text.strip()

    # Проверяем валидность названия
    if not new_name:
        await message.answer("❌ Название не может быть пустым")
        return

    if len(new_name) > 100:
        await message.answer("❌ Название слишком длинное (максимум 100 символов)")
        return

    # Получаем ID магазина из состояния FSM
    state_data = await state.get_data()
    account_id = state_data.get('editing_account_id')

    if not account_id:
        await message.answer("❌ Ошибка: не найден магазин для редактирования")
        await state.clear()
        return

    account_manager = AccountManager(session)
    account = await account_manager.get_account_by_id(account_id)

    if not account:
        await message.answer("❌ Магазин не найден")
        await state.clear()
        return

    current_name = account.account_name or f"Магазин {account.id}"

    # Обновляем название
    updated_account = await account_manager.update_account_name(account_id, new_name)

    if updated_account:
        await message.answer(
            f"✅ <b>Название магазина успешно изменено!</b>\n\n"
            f"Было: <b>{current_name}</b>\n"
            f"Стало: <b>{new_name}</b>",
            reply_markup=get_main_keyboard()
        )
    else:
        await message.answer(
            f"❌ <b>Ошибка при изменении названия</b>\n\n"
            f"Не удалось изменить название магазина.",
            reply_markup=get_main_keyboard()
        )

    # Очищаем состояние
    await state.clear()
