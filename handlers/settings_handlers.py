# settings_handlers.py

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession
from database.account_manager import AccountManager
from handlers.account_handlers import start_add_account, process_api_key, process_account_name
import logging

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
            "❌ <b>Нет магазинов для удаления</b>\n\n"
            "Сначала добавьте магазин в настройках.",
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
        "🗑 <b>Выберите магазин для удаления:</b>",
        reply_markup=builder.as_markup()
    )


@settings_router.callback_query(F.data == "back_to_settings")
async def back_to_settings(callback: CallbackQuery, session: AsyncSession):
    """Возврат к настройкам"""
    await show_settings(callback.message, session)
