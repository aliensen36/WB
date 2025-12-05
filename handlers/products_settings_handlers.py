# handlers/products_settings_handlers.py
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
import math

logger = logging.getLogger(__name__)

products_settings_router = Router()

# Константы для пагинации
ACCOUNTS_PER_PAGE = 5  # Максимальное количество магазинов на странице
PRODUCTS_PER_PAGE = 5  # Максимальное количество товаров на странице


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
    products_text += f"<b>Всего магазинов:</b> {len(all_accounts)}\n"
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

    # Показываем первую страницу магазинов
    await show_accounts_page(callback, session, page=0, action="edit")


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

    # Показываем первую страницу магазинов
    await show_accounts_page(callback, session, page=0, action="show")


async def show_accounts_page(callback: CallbackQuery, session: AsyncSession, page: int, action: str):
    """Показать страницу со списком магазинов"""
    account_manager = AccountManager(session)
    all_accounts = await account_manager.get_all_accounts()

    if not all_accounts:
        return

    total_accounts = len(all_accounts)
    total_pages = math.ceil(total_accounts / ACCOUNTS_PER_PAGE)

    # Проверяем корректность номера страницы
    if page < 0:
        page = 0
    elif page >= total_pages:
        page = total_pages - 1

    # Определяем начало и конец для текущей страницы
    start_idx = page * ACCOUNTS_PER_PAGE
    end_idx = min(start_idx + ACCOUNTS_PER_PAGE, total_accounts)

    builder = InlineKeyboardBuilder()

    # Добавляем кнопки магазинов для текущей страницы
    for account in all_accounts[start_idx:end_idx]:
        account_name = account.account_name or f"Магазин {account.id}"

        # Обрезаем слишком длинные названия
        if len(account_name) > 25:
            account_name = account_name[:22] + "..."

        callback_data = f"select_account_{action}_{account.id}"

        builder.add(InlineKeyboardButton(
            text=f"🏪 {account_name}",
            callback_data=callback_data
        ))

    builder.adjust(1)  # По одной кнопке в строке

    # Добавляем кнопки навигации по страницам, если нужно
    if total_pages > 1:
        navigation_buttons = []

        # Кнопка "Назад" если не первая страница
        if page > 0:
            navigation_buttons.append(InlineKeyboardButton(
                text="◀️ Предыдущая",
                callback_data=f"accounts_page_{action}_{page - 1}"
            ))

        # Индикатор страницы
        navigation_buttons.append(InlineKeyboardButton(
            text=f"📄 {page + 1}/{total_pages}",
            callback_data="noop"
        ))

        # Кнопка "Вперед" если не последняя страница
        if page < total_pages - 1:
            navigation_buttons.append(InlineKeyboardButton(
                text="Следующая ▶️",
                callback_data=f"accounts_page_{action}_{page + 1}"
            ))

        builder.row(*navigation_buttons)

    # Добавляем кнопку "Назад"
    builder.row(InlineKeyboardButton(
        text="⬅️ Назад",
        callback_data="manage_products"
    ))

    action_text = {
        "edit": "изменить название товара",
        "show": "просмотреть список товаров"
    }.get(action, "")

    await callback.message.edit_text(
        f"🏪 <b>Выберите магазин:</b>\n\n"
        f"Выберите магазин, для которого хотите {action_text}.\n"
        f"<b>Всего магазинов:</b> {total_accounts}\n"
        f"<b>Страница:</b> {page + 1}/{total_pages}\n"
        f"<b>Показано магазинов:</b> {start_idx + 1}-{end_idx}",
        reply_markup=builder.as_markup()
    )


@products_settings_router.callback_query(F.data.startswith("accounts_page_"))
async def handle_accounts_pagination(callback: CallbackQuery, session: AsyncSession):
    """Обработка пагинации по магазинам"""
    try:
        # Разбираем callback_data: accounts_page_edit_2 или accounts_page_show_0
        parts = callback.data.split("_")
        action = parts[2]  # edit или show
        page = int(parts[3])  # номер страницы

        await show_accounts_page(callback, session, page, action)
    except Exception as e:
        logger.error(f"Ошибка при пагинации магазинов: {e}")
        await callback.answer("❌ Ошибка переключения страницы")


@products_settings_router.callback_query(F.data.startswith("select_account_"))
async def select_account_for_action(
        callback: CallbackQuery,
        state: FSMContext,
        session: AsyncSession
):
    """Выбор магазина для действия (edit или show)"""
    try:
        # Разбираем callback_data: select_account_edit_123 или select_account_show_456
        parts = callback.data.split("_")
        action = parts[2]  # edit или show
        account_id = int(parts[3])

        if action == "edit":
            await handle_select_account_for_edit(callback, state, session, account_id)
        elif action == "show":
            await handle_select_account_for_show(callback, session, account_id)

    except Exception as e:
        logger.error(f"Ошибка при выборе магазина: {e}")
        await callback.answer("❌ Ошибка выбора магазина")


async def handle_select_account_for_edit(
        callback: CallbackQuery,
        state: FSMContext,
        session: AsyncSession,
        account_id: int
):
    """Обработка выбора магазина для редактирования товаров"""
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

    # Показываем товары с пагинацией (если их много)
    await show_products_page_for_account(callback, session, account, products, page=0, action="edit")


async def handle_select_account_for_show(
        callback: CallbackQuery,
        session: AsyncSession,
        account_id: int
):
    """Обработка выбора магазина для просмотра товаров"""
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

    # Показываем товары с пагинацией (если их много)
    await show_products_page_for_account(callback, session, account, products, page=0, action="show")


async def show_products_page_for_account(
        callback: CallbackQuery,
        session: AsyncSession,
        account,
        products,
        page: int,
        action: str
):
    """Показать страницу с товарами конкретного магазина"""
    total_products = len(products)
    total_pages = math.ceil(total_products / PRODUCTS_PER_PAGE)

    # Проверяем корректность номера страницы
    if page < 0:
        page = 0
    elif page >= total_pages:
        page = total_pages - 1

    # Определяем начало и конец для текущей страницы
    start_idx = page * PRODUCTS_PER_PAGE
    end_idx = min(start_idx + PRODUCTS_PER_PAGE, total_products)

    builder = InlineKeyboardBuilder()

    # Добавляем кнопки товаров для текущей страницы
    for product in products[start_idx:end_idx]:
        display_name = product.custom_name or product.supplier_article
        # Обрезаем слишком длинные названия
        if len(display_name) > 25:  # Уменьшил лимит, т.к. добавляем артикул
            display_name = display_name[:22] + "..."

        # Добавляем артикул перед названием в формате: (артикул) название
        button_text = f"({product.supplier_article}) {display_name}"

        # Обрезаем, если вся строка слишком длинная
        if len(button_text) > 35:
            button_text = button_text[:32] + "..."

        callback_data = f"select_product_{action}_{product.supplier_article}"

        builder.add(InlineKeyboardButton(
            text=button_text,
            callback_data=callback_data
        ))

    builder.adjust(1)

    # Добавляем кнопки навигации по страницам, если нужно
    if total_pages > 1:
        navigation_buttons = []

        if page > 0:
            navigation_buttons.append(InlineKeyboardButton(
                text="◀️ Предыдущая",
                callback_data=f"products_page_{account.id}_{action}_{page - 1}"
            ))

        navigation_buttons.append(InlineKeyboardButton(
            text=f"📄 {page + 1}/{total_pages}",
            callback_data="noop"
        ))

        if page < total_pages - 1:
            navigation_buttons.append(InlineKeyboardButton(
                text="Следующая ▶️",
                callback_data=f"products_page_{account.id}_{action}_{page + 1}"
            ))

        builder.row(*navigation_buttons)

    # Кнопка "Назад" в зависимости от действия
    back_callback = "edit_product_name" if action == "edit" else "show_all_products"
    builder.row(InlineKeyboardButton(
        text="⬅️ Назад к магазинам",
        callback_data=back_callback
    ))

    account_name = account.account_name or f"Магазин {account.id}"

    await callback.message.edit_text(
        f"🏪 <b>Магазин: {account_name}</b>\n\n"
        f"📦 <b>Выберите товар:</b>\n"
        f"<b>Всего товаров в магазине:</b> {total_products}\n"
        f"<b>Страница товаров:</b> {page + 1}/{total_pages}\n"
        f"<b>Показано товаров:</b> {start_idx + 1}-{end_idx}",
        reply_markup=builder.as_markup()
    )


@products_settings_router.callback_query(F.data.startswith("products_page_"))
async def handle_products_pagination(callback: CallbackQuery, session: AsyncSession):
    """Обработка пагинации по товарам"""
    try:
        # Разбираем callback_data: products_page_123_edit_2
        parts = callback.data.split("_")
        account_id = int(parts[2])
        action = parts[3]  # edit или show
        page = int(parts[4])

        account_manager = AccountManager(session)
        account = await account_manager.get_account_by_id(account_id)

        if not account:
            await callback.answer("❌ Магазин не найден")
            return

        product_manager = ProductManager(session)
        products = await product_manager.get_all_products(account_id)

        await show_products_page_for_account(callback, session, account, products, page, action)
    except Exception as e:
        logger.error(f"Ошибка при пагинации товаров: {e}")
        await callback.answer("❌ Ошибка переключения страницы")


@products_settings_router.callback_query(F.data.startswith("select_product_"))
async def select_product_for_action(
        callback: CallbackQuery,
        state: FSMContext,
        session: AsyncSession
):
    """Выбор товара для действия (edit или show)"""
    try:
        # Разбираем callback_data: select_product_edit_ABC123 или select_product_show_DEF456
        parts = callback.data.split("_")
        action = parts[2]  # edit или show
        supplier_article = "_".join(parts[3:])  # Восстанавливаем артикул

        if action == "edit":
            await handle_select_product_for_edit(callback, state, session, supplier_article)
        elif action == "show":
            await handle_select_product_for_show(callback, session, supplier_article)

    except Exception as e:
        logger.error(f"Ошибка при выборе товара: {e}")
        await callback.answer("❌ Ошибка выбора товара")


async def handle_select_product_for_edit(
        callback: CallbackQuery,
        state: FSMContext,
        session: AsyncSession,
        supplier_article: str
):
    """Обработка выбора товара для редактирования"""
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


async def handle_select_product_for_show(
        callback: CallbackQuery,
        session: AsyncSession,
        supplier_article: str
):
    """Обработка выбора товара для просмотра"""
    # Показываем детальную информацию о товаре
    # Находим товар в базе
    product_manager = ProductManager(session)

    # Нужно найти, к какому магазину принадлежит товар
    account_manager = AccountManager(session)
    all_accounts = await account_manager.get_all_accounts()

    found_account = None
    found_product = None

    for account in all_accounts:
        products = await product_manager.get_all_products(account.id)
        for product in products:
            if product.supplier_article == supplier_article:
                found_account = account
                found_product = product
                break
        if found_product:
            break

    if not found_product:
        await callback.answer("❌ Товар не найден")
        return

    account_name = found_account.account_name or f"Магазин {found_account.id}"
    display_name = found_product.custom_name or supplier_article

    builder = InlineKeyboardBuilder()
    builder.add(InlineKeyboardButton(
        text="⬅️ Назад к товарам",
        callback_data=f"show_products_account_{found_account.id}"
    ))

    await callback.message.edit_text(
        f"📦 <b>Информация о товаре</b>\n\n"
        f"🏪 <b>Магазин:</b> {account_name}\n"
        f"📋 <b>Артикул поставщика:</b> <code>{supplier_article}</code>\n"
        f"📝 <b>Название в системе:</b> {display_name}\n\n"
        f"<i>Чтобы изменить название, нажмите \"📝 Изменить название товара\" в меню управления товарами</i>",
        reply_markup=builder.as_markup(),
        parse_mode="HTML"
    )


@products_settings_router.callback_query(F.data.startswith("show_products_account_"))
async def show_products_for_account_from_detail(
        callback: CallbackQuery,
        session: AsyncSession
):
    """Возврат к списку товаров магазина из детального просмотра"""
    account_id = int(callback.data.split("_")[-1])

    account_manager = AccountManager(session)
    account = await account_manager.get_account_by_id(account_id)

    if not account:
        await callback.answer("❌ Магазин не найден")
        return

    product_manager = ProductManager(session)
    products = await product_manager.get_all_products(account_id)

    await show_products_page_for_account(callback, session, account, products, page=0, action="show")


# Остальной код остается без изменений
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


@products_settings_router.callback_query(F.data == "back_to_settings")
async def back_to_settings(callback: CallbackQuery, session: AsyncSession):
    """Возврат к главному меню настроек"""
    await show_settings(callback, session)