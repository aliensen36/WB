# handlers/product_handlers.py
from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardButton, Message
from sqlalchemy.ext.asyncio import AsyncSession

from FSM.account_states import AccountManagementStates
from database.account_manager import AccountManager
from keyboards.settings_kb import get_products_management_keyboard, get_back_to_settings_keyboard

product_router = Router()

@product_router.callback_query(F.data == "products_list")
async def show_products_list(callback: CallbackQuery, session: AsyncSession):
    """Показать список продуктов"""
    # Сначала нужно выбрать магазин
    account_manager = AccountManager(session)
    all_accounts = await account_manager.get_all_accounts()

    if not all_accounts:
        await callback.message.edit_text(
            "<b>Нет магазинов для просмотра продуктов</b>",
            reply_markup=get_products_management_keyboard()
        )
        return

    from aiogram.utils.keyboard import InlineKeyboardBuilder

    builder = InlineKeyboardBuilder()
    for account in all_accounts:
        account_name = account.account_name or f"Магазин {account.id}"
        builder.add(InlineKeyboardButton(
            text=f"📋 {account_name}",
            callback_data=f"list_products_{account.id}"
        ))
    builder.add(InlineKeyboardButton(text="⬅️ Назад", callback_data="manage_products"))
    builder.adjust(1)

    await callback.message.edit_text(
        "<b>Выберите магазин для просмотра продуктов:</b>",
        reply_markup=builder.as_markup()
    )


@product_router.callback_query(F.data.startswith("list_products_"))
async def list_products(callback: CallbackQuery, session: AsyncSession):
    """Показать продукты выбранного магазина"""
    account_id = int(callback.data.split("_")[2])

    account_manager = AccountManager(session)
    account = await account_manager.get_account_by_id(account_id)

    if not account:
        await callback.answer("❌ Магазин не найден")
        return

    # Получаем продукты магазина
    from database.product_manager import ProductManager
    product_manager = ProductManager(session)
    products = await product_manager.get_products_by_account(account_id)

    account_name = account.account_name or f"Магазин {account.id}"

    from aiogram.utils.keyboard import InlineKeyboardBuilder

    builder = InlineKeyboardBuilder()

    if products:
        products_text = f"📋 <b>Продукты магазина \"{account_name}\"</b>\n\n"

        for i, product in enumerate(products, 1):
            product_name = product.custom_name or product.supplier_article
            products_text += f"{i}. <b>{product_name}</b>\n"
            products_text += f"   Артикул: {product.supplier_article}\n"

        products_text += f"\n📊 <b>Всего продуктов: {len(products)}</b>"

        builder.add(InlineKeyboardButton(text="✏️ Изменить названия",
                                         callback_data=f"edit_account_products_{account_id}"))
    else:
        products_text = (
            f"📦 <b>Продукты магазина \"{account_name}\"</b>\n\n"
            f"📭 <i>В этом магазине пока нет продуктов</i>"
        )

    builder.add(InlineKeyboardButton(text="⬅️ Назад", callback_data="products_list"))
    builder.adjust(1)

    await callback.message.edit_text(
        products_text,
        reply_markup=builder.as_markup()
    )


@product_router.callback_query(F.data == "edit_products")
async def edit_products(callback: CallbackQuery, session: AsyncSession):
    """Начать редактирование продуктов"""
    account_manager = AccountManager(session)
    all_accounts = await account_manager.get_all_accounts()

    if not all_accounts:
        await callback.message.edit_text(
            "<b>Нет магазинов для редактирования продуктов</b>",
            reply_markup=get_products_management_keyboard()
        )
        return

    from aiogram.utils.keyboard import InlineKeyboardBuilder

    builder = InlineKeyboardBuilder()
    for account in all_accounts:
        account_name = account.account_name or f"Магазин {account.id}"
        builder.add(InlineKeyboardButton(
            text=f"✏️ {account_name}",
            callback_data=f"edit_account_products_{account.id}"
        ))
    builder.add(InlineKeyboardButton(text="⬅️ Назад", callback_data="manage_products"))
    builder.adjust(1)

    await callback.message.edit_text(
        "<b>Выберите магазин для изменения названий продуктов:</b>",
        reply_markup=builder.as_markup()
    )


@product_router.callback_query(F.data.startswith("edit_account_products_"))
async def start_edit_account_products(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Начать редактирование продуктов магазина"""
    account_id = int(callback.data.split("_")[3])

    account_manager = AccountManager(session)
    account = await account_manager.get_account_by_id(account_id)

    if not account:
        await callback.answer("❌ Магазин не найден")
        return

    # Получаем продукты магазина
    from database.product_manager import ProductManager
    product_manager = ProductManager(session)
    products = await product_manager.get_products_by_account(account_id)

    if not products:
        await callback.message.edit_text(
            f"📦 <b>Магазин \"{account.account_name}\"</b>\n\n"
            f"📭 <i>В этом магазине пока нет продуктов для редактирования</i>",
            reply_markup=get_back_to_settings_keyboard()
        )
        return

    account_name = account.account_name or f"Магазин {account.id}"

    # Сохраняем информацию о редактируемых продуктах в состоянии
    await state.update_data(
        editing_products_account_id=account_id,
        products_list=[{"id": p.id, "supplier_article": p.supplier_article,
                        "current_name": p.custom_name or p.supplier_article} for p in products]
    )

    # Показываем первый продукт для редактирования
    await state.update_data(current_product_index=0)
    await show_product_for_editing(callback, state, session)


async def show_product_for_editing(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Показать продукт для редактирования"""
    state_data = await state.get_data()
    products_list = state_data.get("products_list", [])
    current_index = state_data.get("current_product_index", 0)
    account_id = state_data.get("editing_products_account_id")

    if not products_list or current_index >= len(products_list):
        await finish_editing_products(callback, state, session)
        return

    product = products_list[current_index]

    from aiogram.utils.keyboard import InlineKeyboardBuilder

    builder = InlineKeyboardBuilder()

    # Если есть следующий продукт
    if current_index < len(products_list) - 1:
        builder.add(InlineKeyboardButton(text="➡️ Пропустить",
                                         callback_data="skip_product_edit"))
    else:
        builder.add(InlineKeyboardButton(text="✅ Завершить",
                                         callback_data="finish_editing"))

    builder.add(InlineKeyboardButton(text="❌ Отмена",
                                     callback_data="cancel_editing_products"))
    builder.adjust(2)

    account_manager = AccountManager(session)
    account = await account_manager.get_account_by_id(account_id)
    account_name = account.account_name if account else f"Магазин {account_id}"

    edit_text = (
        f"✏️ <b>Редактирование названий продуктов</b>\n"
        f"Магазин: <b>{account_name}</b>\n\n"
        f"Продукт {current_index + 1} из {len(products_list)}:\n"
        f"Артикул: <code>{product['supplier_article']}</code>\n"
        f"Текущее название: <b>{product['current_name']}</b>\n\n"
        f"Введите новое название для этого продукта:"
    )

    await callback.message.edit_text(
        edit_text,
        reply_markup=builder.as_markup()
    )
    await state.set_state(AccountManagementStates.waiting_product_rename)


@product_router.callback_query(F.data == "skip_product_edit")
async def skip_product_edit(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Пропустить редактирование текущего продукта"""
    state_data = await state.get_data()
    current_index = state_data.get("current_product_index", 0)

    # Переходим к следующему продукту
    await state.update_data(current_product_index=current_index + 1)
    await show_product_for_editing(callback, state, session)


@product_router.callback_query(F.data == "finish_editing")
async def finish_editing(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Завершить редактирование продуктов"""
    await finish_editing_products(callback, state, session)


@product_router.callback_query(F.data == "cancel_editing_products")
async def cancel_editing_products(callback: CallbackQuery, state: FSMContext):
    """Отмена редактирования продуктов"""
    await state.clear()
    await callback.message.edit_text(
        "❌ <b>Редактирование отменено</b>",
        reply_markup=get_back_to_settings_keyboard()
    )


async def finish_editing_products(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Завершение редактирования продуктов"""
    state_data = await state.get_data()
    account_id = state_data.get("editing_products_account_id")

    account_manager = AccountManager(session)
    account = await account_manager.get_account_by_id(account_id)
    account_name = account.account_name if account else f"Магазин {account_id}"

    await state.clear()

    await callback.message.edit_text(
        f"✅ <b>Редактирование продуктов завершено!</b>\n\n"
        f"Магазин: <b>{account_name}</b>\n"
        f"Названия продуктов успешно обновлены.",
        reply_markup=get_back_to_settings_keyboard()
    )


@product_router.message(AccountManagementStates.waiting_product_rename)
async def process_product_rename(message: Message, state: FSMContext, session: AsyncSession):
    """Обработка нового названия продукта"""
    new_name = message.text.strip()

    # Проверяем валидность названия
    if not new_name:
        await message.answer("❌ Название не может быть пустым")
        return

    if len(new_name) > 255:
        await message.answer("❌ Название слишком длинное (максимум 255 символов)")
        return

    # Получаем данные из состояния
    state_data = await state.get_data()
    products_list = state_data.get("products_list", [])
    current_index = state_data.get("current_product_index", 0)

    if current_index >= len(products_list):
        await message.answer("❌ Ошибка: продукт не найден")
        await state.clear()
        return

    # Обновляем название продукта в базе данных
    product_id = products_list[current_index]["id"]

    from database.product_manager import ProductManager
    product_manager = ProductManager(session)
    success = await product_manager.update_product_custom_name(product_id, new_name)

    if success:
        # Обновляем название в списке состояний
        products_list[current_index]["current_name"] = new_name
        await state.update_data(products_list=products_list)

        # Переходим к следующему продукту
        await state.update_data(current_product_index=current_index + 1)

        # Показываем следующий продукт или завершаем
        from aiogram.types import CallbackQuery
        mock_callback = CallbackQuery(
            message=message,
            id="temp",
            chat_instance="temp",
            data="temp"
        )
        await show_product_for_editing(mock_callback, state, session)
    else:
        await message.answer("❌ Ошибка при обновлении названия продукта")
        await state.clear()

