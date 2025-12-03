# products_settings_handlers.py
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession
from aiogram.utils.keyboard import InlineKeyboardBuilder
from FSM.account_states import AccountManagementStates, AddAccountStates
from FSM.product_states import ProductManagementStates
from database.account_manager import AccountManager
from database.product_manager import ProductManager
from handlers.accounts_settings_handlers import handle_cancel
from handlers.settings_handlers import show_settings
from keyboards.account_kb import get_shops_management_keyboard, get_cancel_inline_keyboard
from keyboards.product_kb import get_products_management_keyboard
from keyboards.settings_kb import get_settings_keyboard
import logging

logger = logging.getLogger(__name__)

products_settings_router = Router()


@products_settings_router.callback_query(F.data == "manage_products")
async def manage_products(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Переход к управлению товарами"""
    account_manager = AccountManager(session)
    all_accounts = await account_manager.get_all_accounts()

    if not all_accounts:
        await callback.message.edit_text(
            "📭 <b>Нет магазинов для управления товарами</b>\n\n"
            "Сначала добавьте магазин, чтобы управлять товарами.",
            reply_markup=get_settings_keyboard()
        )
        return

    products_text = "📦 <b>Управление товарами</b>\n\n"
    products_text += "Здесь вы можете:\n"
    products_text += "• 📝 Изменить название товара для отчетов\n"
    products_text += "• 📋 Просмотреть список всех товаров\n\n"
    products_text += "Выберите действие:"

    await callback.message.edit_text(
        products_text,
        reply_markup=get_products_management_keyboard()
    )


@products_settings_router.callback_query(F.data == "edit_product_name")
async def edit_product_name_start(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Начало процесса изменения названия товара"""
    account_manager = AccountManager(session)
    all_accounts = await account_manager.get_all_accounts()

    if not all_accounts:
        await callback.message.edit_text(
            "📭 <b>Нет магазинов для управления товарами</b>",
            reply_markup=get_products_management_keyboard()
        )
        return

    builder = InlineKeyboardBuilder()
    for account in all_accounts:
        account_name = account.account_name or f"Магазин {account.id}"
        builder.add(InlineKeyboardButton(
            text=f"🏪 {account_name}",
            callback_data=f"select_account_for_product_{account.id}"
        ))
    builder.add(InlineKeyboardButton(text="⬅️ Назад", callback_data="manage_products"))
    builder.adjust(1)

    await callback.message.edit_text(
        "🏪 <b>Выберите магазин:</b>\n\n"
        "Выберите магазин, для которого хотите изменить название товара:",
        reply_markup=builder.as_markup()
    )
    await state.set_state(ProductManagementStates.waiting_for_account_selection)


@products_settings_router.callback_query(F.data.startswith("select_account_for_product_"))
async def select_account_for_product(
        callback: CallbackQuery,
        state: FSMContext,
        session: AsyncSession
):
    """Выбор магазина для изменения названия товара"""
    account_id = int(callback.data.split("_")[-1])

    # Сохраняем ID магазина в состоянии
    await state.update_data(account_id=account_id)

    account_manager = AccountManager(session)
    account = await account_manager.get_account_by_id(account_id)

    if not account:
        await callback.answer("❌ Магазин не найден")
        return

    product_manager = ProductManager(session)
    products = await product_manager.get_all_products(account_id)

    if not products:
        builder = InlineKeyboardBuilder()
        builder.add(InlineKeyboardButton(text="⬅️ Назад", callback_data="edit_product_name"))

        await callback.message.edit_text(
            f"📭 <b>В магазине \"{account.account_name or f'Магазин {account.id}'}\" нет товаров</b>\n\n"
            f"Добавьте товары через функционал выгрузки отчетов, чтобы можно было изменить их названия.",
            reply_markup=builder.as_markup()
        )
        await state.clear()
        return

    builder = InlineKeyboardBuilder()

    # Показываем только первые 50 товаров для удобства
    for product in products[:50]:
        display_name = product.custom_name or product.supplier_article
        # Обрезаем слишком длинные названия
        if len(display_name) > 30:
            display_name = display_name[:27] + "..."

        builder.add(InlineKeyboardButton(
            text=f"📦 {display_name}",
            callback_data=f"select_product_{product.supplier_article}"
        ))

    # Если товаров больше 50, добавляем сообщение
    if len(products) > 50:
        builder.add(InlineKeyboardButton(
            text=f"📋 Показано 50 из {len(products)} товаров",
            callback_data="noop"
        ))

    builder.add(InlineKeyboardButton(text="⬅️ Назад", callback_data="edit_product_name"))
    builder.adjust(1)

    account_name = account.account_name or f"Магазин {account.id}"

    await callback.message.edit_text(
        f"🏪 <b>Магазин: {account_name}</b>\n\n"
        f"📦 <b>Выберите товар для изменения названия:</b>\n"
        f"<i>(Всего товаров: {len(products)})</i>",
        reply_markup=builder.as_markup()
    )
    await state.set_state(ProductManagementStates.waiting_for_article_selection)


@products_settings_router.callback_query(
    ProductManagementStates.waiting_for_article_selection,
    F.data.startswith("select_product_")
)
async def select_product_for_rename(
        callback: CallbackQuery,
        state: FSMContext,
        session: AsyncSession
):
    """Выбор товара для изменения названия"""
    supplier_article = callback.data.replace("select_product_", "")

    # Получаем данные из состояния
    data = await state.get_data()
    account_id = data.get("account_id")

    if not account_id:
        await callback.answer("❌ Ошибка данных")
        return

    # Сохраняем артикул в состоянии
    await state.update_data(supplier_article=supplier_article)

    product_manager = ProductManager(session)
    account_manager = AccountManager(session)

    account = await account_manager.get_account_by_id(account_id)
    account_name = account.account_name or f"Магазин {account.id}"

    # Получаем текущее название товара
    products = await product_manager.get_all_products(account_id)
    current_product = None
    for product in products:
        if product.supplier_article == supplier_article:
            current_product = product
            break

    if not current_product:
        await callback.answer("❌ Товар не найден")
        return

    current_name = current_product.custom_name or supplier_article

    cancel_kb = get_cancel_inline_keyboard()

    await callback.message.edit_text(
        f"🏪 <b>Магазин:</b> {account_name}\n"
        f"📦 <b>Артикул:</b> {supplier_article}\n"
        f"📝 <b>Текущее название:</b> {current_name}\n\n"
        f"<b>Введите новое название для товара:</b>\n"
        f"<i>Или нажмите \"❌ Отмена\" для отмены</i>",
        reply_markup=cancel_kb
    )
    await state.set_state(ProductManagementStates.waiting_for_new_name)


@products_settings_router.callback_query(F.data == "noop")
async def handle_noop(callback: CallbackQuery):
    """Обработчик для кнопок без действия"""
    await callback.answer()


@products_settings_router.message(ProductManagementStates.waiting_for_new_name)
async def process_new_product_name(
        message: Message,
        state: FSMContext,
        session: AsyncSession
):
    """Обработка нового названия товара"""
    if message.text == "❌ Отмена":
        await handle_cancel(message, state)
        return

    new_name = message.text.strip()

    if not new_name:
        cancel_kb = get_cancel_inline_keyboard()
        await message.answer(
            "❌ <b>Название не может быть пустым</b>\n\n"
            "Пожалуйста, введите название товара:\n"
            "<i>Или нажмите \"❌ Отмена\" для отмены</i>",
            reply_markup=cancel_kb
        )
        return

    if len(new_name) > 200:
        cancel_kb = get_cancel_inline_keyboard()
        await message.answer(
            "❌ <b>Слишком длинное название</b>\n\n"
            "Название товара не должно превышать 200 символов.\n"
            "Пожалуйста, введите более короткое название:\n"
            "<i>Или нажмите \"❌ Отмена\" для отмены</i>",
            reply_markup=cancel_kb
        )
        return

    # Получаем данные из состояния
    data = await state.get_data()
    account_id = data.get("account_id")
    supplier_article = data.get("supplier_article")

    if not account_id or not supplier_article:
        await message.answer(
            "❌ <b>Ошибка данных</b>\n\n"
            "Не удалось определить товар для редактирования.",
            reply_markup=get_products_management_keyboard()
        )
        await state.clear()
        return

    # Обновляем название товара
    product_manager = ProductManager(session)
    account_manager = AccountManager(session)

    account = await account_manager.get_account_by_id(account_id)
    account_name = account.account_name or f"Магазин {account.id}"

    success = await product_manager.update_custom_name(
        seller_account_id=account_id,
        supplier_article=supplier_article,
        custom_name=new_name
    )

    if success:
        builder = InlineKeyboardBuilder()
        builder.add(
            InlineKeyboardButton(text="📝 Изменить еще товар", callback_data="edit_product_name"),
            InlineKeyboardButton(text="🏪 К управлению товарами", callback_data="manage_products")
        )
        builder.adjust(1)

        await message.answer(
            f"✅ <b>Название товара успешно изменено!</b>\n\n"
            f"🏪 <b>Магазин:</b> {account_name}\n"
            f"📦 <b>Артикул:</b> {supplier_article}\n"
            f"📝 <b>Новое название:</b> {new_name}",
            reply_markup=builder.as_markup()
        )
    else:
        await message.answer(
            "❌ <b>Ошибка при изменении названия</b>\n\n"
            "Не удалось изменить название товара.\n"
            "Попробуйте еще раз.",
            reply_markup=get_products_management_keyboard()
        )

    # Очищаем состояние
    await state.clear()


@products_settings_router.callback_query(F.data == "show_all_products")
async def show_all_products_start(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Показать все товары"""
    account_manager = AccountManager(session)
    all_accounts = await account_manager.get_all_accounts()

    if not all_accounts:
        await callback.message.edit_text(
            "📭 <b>Нет магазинов для отображения товаров</b>",
            reply_markup=get_products_management_keyboard()
        )
        return

    builder = InlineKeyboardBuilder()
    for account in all_accounts:
        account_name = account.account_name or f"Магазин {account.id}"
        builder.add(InlineKeyboardButton(
            text=f"🏪 {account_name}",
            callback_data=f"show_products_account_{account.id}"
        ))
    builder.add(InlineKeyboardButton(text="⬅️ Назад", callback_data="manage_products"))
    builder.adjust(1)

    await callback.message.edit_text(
        "🏪 <b>Выберите магазин:</b>\n\n"
        "Выберите магазин, для которого хотите просмотреть список товаров:",
        reply_markup=builder.as_markup()
    )


@products_settings_router.callback_query(F.data.startswith("show_products_account_"))
async def show_products_for_account(
        callback: CallbackQuery,
        session: AsyncSession
):
    """Показать товары для выбранного магазина"""
    account_id = int(callback.data.split("_")[-1])

    account_manager = AccountManager(session)
    account = await account_manager.get_account_by_id(account_id)

    if not account:
        await callback.answer("❌ Магазин не найден")
        return

    product_manager = ProductManager(session)
    products = await product_manager.get_all_products(account_id)

    account_name = account.account_name or f"Магазин {account.id}"

    if not products:
        builder = InlineKeyboardBuilder()
        builder.add(InlineKeyboardButton(text="⬅️ Назад", callback_data="show_all_products"))

        await callback.message.edit_text(
            f"📭 <b>В магазине \"{account_name}\" нет товаров</b>\n\n"
            f"Добавьте товары через функционал выгрузки отчетов.",
            reply_markup=builder.as_markup()
        )
        return

    # Формируем сообщение с товарами
    products_text = f"🏪 <b>Магазин:</b> {account_name}\n"
    products_text += f"📦 <b>Всего товаров:</b> {len(products)}\n\n"
    products_text += "<b>Список товаров:</b>\n"

    for i, product in enumerate(products, 1):
        display_name = product.custom_name or product.supplier_article
        products_text += f"{i}. <code>{product.supplier_article}</code> - {display_name}\n"

        # Ограничиваем длину сообщения
        if i % 20 == 0 and i < len(products):
            # Добавляем продолжение
            products_text += f"\n... и еще {len(products) - i} товаров"
            break

    # Создаем клавиатуру - сначала основное действие, потом навигация
    builder = InlineKeyboardBuilder()
    builder.add(InlineKeyboardButton(text="📝 Изменить название", callback_data="edit_product_name"))
    builder.add(InlineKeyboardButton(text="⬅️ Назад", callback_data="show_all_products"))
    builder.adjust(1)  # Каждая кнопка на отдельной строке

    await callback.message.edit_text(
        products_text,
        reply_markup=builder.as_markup(),
        parse_mode="HTML"
    )



@products_settings_router.callback_query(F.data == "back_to_settings")
async def back_to_settings(callback: CallbackQuery, session: AsyncSession):
    """Возврат к главному меню настроек"""
    await show_settings(callback, session)
