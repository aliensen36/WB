# handlers/yesterday_product_statistics_handlers.py
import asyncio
import logging
from datetime import datetime, timedelta
from aiogram import Router, F
from aiogram.types import CallbackQuery, Message, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.state import State, StatesGroup
from sqlalchemy.ext.asyncio import AsyncSession
from database.account_manager import AccountManager
from database.product_manager import ProductManager
from functions.yesterday_product_statistics import YesterdayProductStatistics
from keyboards.statistics_kb import get_stats_keyboard

logger = logging.getLogger(__name__)

yesterday_product_statistics_router = Router()

# Хранилище для данных пользователей (временное решение, лучше использовать Redis)
user_data_store = {}


# Состояния
class StatisticsState(StatesGroup):
    waiting = State()


@yesterday_product_statistics_router.callback_query(F.data == "yesterday_stats")
async def handle_yesterday_stats(callback: CallbackQuery, session: AsyncSession):
    """Показать детальную статистику по товарам за вчера для всех магазинов"""

    await callback.answer()

    logger.info("Получение статистики за вчера")

    try:
        loading_msg = await callback.message.answer(
            "⏳ Получение статистики по товарам за вчера...\n"
            "Это может занять несколько минут."
        )

        account_manager = AccountManager(session)
        all_accounts = await account_manager.get_all_accounts()

        if not all_accounts:
            await loading_msg.delete()
            await callback.message.answer(
                "❌ Нет добавленных магазинов",
                reply_markup=get_stats_keyboard()
            )
            return

        logger.info(f"Найдено магазинов для обработки: {len(all_accounts)}")

        successful_accounts = 0
        failed_accounts = 0

        # Получаем дату вчерашнего дня
        yesterday_date_obj = datetime.now() - timedelta(days=1)
        date_str = yesterday_date_obj.strftime("%d.%m.%Y")
        days = ["Понедельник", "Вторник", "Среда", "Четверг", "Пятница", "Суббота", "Воскресенье"]
        day_name = days[yesterday_date_obj.weekday()]

        # Инициализируем хранилище для пользователя
        user_id = callback.from_user.id
        user_data_store[user_id] = {
            "account_index": 0,
            "store_index": 0,
            "current_page": {},
            "store_data": {},
            "stores_order": [],  # Порядок магазинов для навигации
            "total_accounts": len(all_accounts),
            "date_str": date_str,
            "day_name": day_name,
            "successful_accounts": 0,
            "failed_accounts": 0
        }

        # Обрабатываем каждый магазин
        stores_order = []

        for account_index, account in enumerate(all_accounts, 1):
            account_name = account.account_name or f"Магазин {account.id}"
            logger.info(f"[{account_index}/{len(all_accounts)}] Обрабатываю магазин: {account_name}")

            try:
                # Обновляем сообщение о загрузке
                try:
                    await loading_msg.edit_text(
                        f"⏳ Получение статистики...\n"
                        f"Обработка магазина {account_index}/{len(all_accounts)}\n"
                        f"<i>{account_name}</i>"
                    )
                except:
                    pass

                # Получаем комбинированную статистику для текущего магазина
                yesterday_stats = YesterdayProductStatistics(account.api_key)
                combined_stats = await yesterday_stats.get_combined_yesterday_stats()

                # Извлекаем данные из комбинированной статистики
                funnel_stats = combined_stats.get("funnel_stats", {})
                sales_stats = combined_stats.get("sales_stats", {})
                recommended_stats = combined_stats.get("recommended_stats", {})

                logger.info(f"[{account_name}] Товаров: {funnel_stats.get('total_products', 0)}")
                logger.info(f"[{account_name}] Заказов: {funnel_stats.get('total_orders', 0)}")
                logger.info(
                    f"[{account_name}] Выкупов: {recommended_stats.get('total_buyouts', 0)} шт. на {recommended_stats.get('total_buyout_sum', 0):.2f} руб.")

                # Получаем детальные данные по товарам
                try:
                    stats_obj = YesterdayProductStatistics(account.api_key)
                    detailed_stats = await stats_obj.get_yesterday_product_stats()

                    # Сохраняем товары в БД
                    product_manager = ProductManager(session)
                    saved_products_count = 0
                    all_products_for_save = detailed_stats.get("all_products", [])

                    for product_data in all_products_for_save:
                        try:
                            article = product_data.get('article')
                            if article:
                                product = await product_manager.get_or_create_product(
                                    seller_account_id=account.id,
                                    supplier_article=article
                                )
                                saved_products_count += 1

                                title = product_data.get('title')
                                if title and not product.custom_name:
                                    short_title = title[:100] if len(title) > 100 else title
                                    await product_manager.update_custom_name(
                                        seller_account_id=account.id,
                                        supplier_article=article,
                                        custom_name=short_title
                                    )
                        except Exception as e:
                            logger.error(f"Ошибка при сохранении товара: {e}")

                    logger.info(f"[{account_name}] Сохранено товаров: {saved_products_count}")

                except Exception as e:
                    logger.error(f"[{account_name}] Ошибка при получении детальных данных: {e}")
                    detailed_stats = {}

                # Получаем кастомные названия из БД
                product_manager = ProductManager(session)
                custom_names = await product_manager.get_custom_names_dict(account.id)

                # Получаем товары с активностью
                products_with_activity = []
                try:
                    # Пробуем получить товары из детальной статистики
                    products_with_orders = detailed_stats.get("products", [])
                    if not products_with_orders:
                        # Если нет товаров, пробуем получить из другой структуры данных
                        all_products = detailed_stats.get("all_products", [])
                        # Фильтруем товары с заказами или выкупами
                        products_with_activity = [p for p in all_products if
                                                  p.get('orders', 0) > 0 or p.get('buyouts', 0) > 0]
                    else:
                        # Фильтруем только товары с активностью
                        products_with_activity = [p for p in products_with_orders if
                                                  p.get('orders', 0) > 0 or p.get('buyouts', 0) > 0]

                    # СОРТИРУЕМ ТОВАРЫ ПО КОЛИЧЕСТВУ ЗАКАЗОВ (от большего к меньшему)
                    products_with_activity.sort(key=lambda x: x.get('orders', 0), reverse=True)

                except Exception as e:
                    logger.error(f"[{account_name}] Ошибка при получении товаров с активностью: {e}")
                    products_with_activity = []

                # Сохраняем данные магазина
                store_data = {
                    "account_name": account_name,
                    "account_id": account.id,
                    "products_with_activity": products_with_activity,
                    "custom_names": custom_names,
                    "funnel_stats": funnel_stats,
                    "sales_stats": sales_stats,
                    "recommended_stats": recommended_stats,
                    "detailed_stats": detailed_stats,
                    "total_views": detailed_stats.get("total_views", 0),
                    "total_carts": detailed_stats.get("total_carts", 0),
                    "overall_cart_conversion": detailed_stats.get("overall_cart_conversion", 0),
                    "overall_order_conversion": detailed_stats.get("overall_order_conversion", 0),
                    "has_activity": len(products_with_activity) > 0
                }

                user_data_store[user_id]["store_data"][account_name] = store_data
                stores_order.append(account_name)

                # Обновляем счетчики
                if funnel_stats.get("total_orders", 0) > 0 or recommended_stats.get("total_buyouts", 0) > 0:
                    successful_accounts += 1
                    user_data_store[user_id]["successful_accounts"] = successful_accounts
                else:
                    failed_accounts += 1
                    user_data_store[user_id]["failed_accounts"] = failed_accounts

            except Exception as e:
                error_message = str(e)
                logger.error(f"[{account_name}] Ошибка при получении статистики: {error_message}")
                failed_accounts += 1
                user_data_store[user_id]["failed_accounts"] = failed_accounts

                # Сохраняем информацию об ошибке
                error_data = {
                    "account_name": account_name,
                    "error": True,
                    "error_message": error_message,
                    "display_error": "Неизвестная ошибка"
                }

                if "Неверный API ключ" in error_message:
                    error_data["display_error"] = "Неверный API ключ"
                elif "Превышен лимит запросов" in error_message:
                    error_data["display_error"] = "Превышен лимит запросов API"
                elif "Таймаут запроса" in error_message:
                    error_data["display_error"] = "Таймаут запроса"
                else:
                    error_data["display_error"] = "Ошибка подключения к API"

                user_data_store[user_id]["store_data"][account_name] = error_data
                stores_order.append(account_name)

            # Задержка между запросами к разным магазинам
            if account_index < len(all_accounts):
                await asyncio.sleep(5)

        # Сохраняем порядок магазинов
        user_data_store[user_id]["stores_order"] = stores_order

        # Удаляем сообщение о загрузке
        try:
            await loading_msg.delete()
        except:
            pass

        # Отправляем заголовок статистики
        header_text = (f"<b>📊 СТАТИСТИКА ЗА ВЧЕРА</b>\n"
                       f"📅 {date_str} ({day_name})\n"
                       f"Всего магазинов: {len(all_accounts)}\n"
                       f"Успешно: {successful_accounts} | Ошибок: {failed_accounts}\n\n"
                       f"<i>Используйте кнопки для навигации</i>")

        header_msg = await callback.message.answer(header_text)

        # Сохраняем ID сообщения с заголовком для возможного редактирования
        user_data_store[user_id]["header_message_id"] = header_msg.message_id

        # Показываем первый магазин или ошибку
        if stores_order:
            first_store = stores_order[0]
            store_data = user_data_store[user_id]["store_data"].get(first_store)

            if store_data.get("error", False):
                # Показываем ошибку
                await show_error_message(callback.message, user_id, first_store, store_data)
            elif store_data.get("has_activity", False):
                # Показываем первую страницу товаров
                await show_store_page(callback.message, user_id, first_store, 1)
            else:
                # Показываем статистику без товаров
                await show_store_summary(callback.message, user_id, first_store, store_data)
        else:
            await callback.message.answer("❌ Не удалось получить данные ни от одного магазина")

        logger.info(f"Статистика успешно отправлена для {successful_accounts}/{len(all_accounts)} магазинов")

    except Exception as e:
        logger.error(f"Неожиданная ошибка при получении статистики за вчера: {e}")
        try:
            await loading_msg.delete()
        except:
            pass

        await callback.message.answer(
            f"<b>❌ Произошла непредвиденная ошибка</b>\n"
            f"<i>Детали: {str(e)[:100]}</i>\n"
            "Попробуйте позже.",
            reply_markup=get_stats_keyboard()
        )


async def show_store_page(message: Message, user_id: int, store_name: str, page: int = 1, edit_message: Message = None):
    """Показывает страницу с товарами магазина (с замещением предыдущей)"""

    if user_id not in user_data_store:
        await message.answer("❌ Данные устарели. Запросите статистику заново.")
        return

    store_data = user_data_store[user_id]["store_data"].get(store_name)
    if not store_data or store_data.get("error", False):
        await message.answer(f"❌ Данные для магазина '{store_name}' не найдены или содержат ошибку.")
        return

    products_with_activity = store_data.get("products_with_activity", [])
    custom_names = store_data.get("custom_names", {})

    # Параметры пагинации
    PRODUCTS_PER_PAGE = 3
    total_products = len(products_with_activity)
    total_pages = (total_products + PRODUCTS_PER_PAGE - 1) // PRODUCTS_PER_PAGE if total_products > 0 else 1

    # Ограничиваем номер страницы
    page = max(1, min(page, total_pages))

    # Сохраняем текущую страницу
    user_data_store[user_id]["current_page"][store_name] = page

    # Определяем текущий индекс магазина в списке
    stores_order = user_data_store[user_id]["stores_order"]
    current_index = stores_order.index(store_name) if store_name in stores_order else -1
    total_stores = len(stores_order)

    # Рассчитываем индексы товаров
    start_idx = (page - 1) * PRODUCTS_PER_PAGE
    end_idx = min(start_idx + PRODUCTS_PER_PAGE, total_products)
    current_products = products_with_activity[start_idx:end_idx]

    # Формируем текст сообщения
    text = f"<b>{store_name}</b>\n\n"

    # Добавляем товары
    for i, product in enumerate(current_products, start_idx + 1):
        # Берем кастомное название из БД, если есть, иначе название из API
        article = product.get('article', '')
        display_name = custom_names.get(article)
        if not display_name:
            display_name = product.get('title', '')

        # Форматируем числа
        views_formatted = f"{product.get('views', 0):,}"
        carts_formatted = f"{product.get('carts', 0):,}"
        orders_formatted = f"{product.get('orders', 0):,}"
        order_sum_formatted = f"{product.get('order_sum', 0):,.2f} ₽".replace(",", " ").replace(".", ",")

        # Выкупы
        buyouts = product.get('buyouts', 0)
        buyout_sum = product.get('buyout_sum', 0)

        buyouts_formatted = f"{buyouts:,}"
        buyout_sum_formatted = f"{buyout_sum:,.2f} ₽".replace(",", " ").replace(".", ",")

        # Добавляем товар
        text += f"<b>{i}. ({article}) {display_name}</b>\n"
        text += f"Просмотров: {views_formatted}   В корзине: {carts_formatted}\n"
        text += f"Конверсия: в корзину {product.get('conversion_to_cart', 0):.1f}%, в заказ: {product.get('conversion_to_order', 0):.1f}%\n"
        text += f"<b>Заказы: {orders_formatted} шт. на {order_sum_formatted}</b>\n\n"

    # Добавляем информацию о странице в конец сообщения
    text += f"Страница {page}/{total_pages} | Товары {start_idx + 1}-{end_idx} из {total_products}\n"
    text += f"Магазин {current_index + 1}/{total_stores}"

    # Создаем клавиатуру
    keyboard = []

    # Кнопки навигации по страницам (только влево-вправо)
    nav_buttons = []
    if page > 1:
        nav_buttons.append(InlineKeyboardButton(text="◀️ Назад", callback_data=f"page:{store_name}:{page - 1}"))

    if page < total_pages:
        nav_buttons.append(InlineKeyboardButton(text="Вперед ▶️", callback_data=f"page:{store_name}:{page + 1}"))

    if nav_buttons:
        keyboard.append(nav_buttons)

    # Кнопки навигации между магазинами
    store_nav_buttons = []
    if current_index > 0:
        prev_store = stores_order[current_index - 1]
        store_nav_buttons.append(InlineKeyboardButton(text="⏪ Пред. магазин", callback_data=f"store:{prev_store}:1"))

    # Кнопки действий
    action_buttons = []
    action_buttons.append(InlineKeyboardButton(text="📊 Итоги", callback_data=f"summary:{store_name}"))

    if current_index >= 0 and current_index < total_stores - 1:
        next_store = stores_order[current_index + 1]
        store_nav_buttons.append(InlineKeyboardButton(text="След. магазин ⏩", callback_data=f"store:{next_store}:1"))

    if store_nav_buttons:
        keyboard.append(store_nav_buttons)

    if action_buttons:
        keyboard.append(action_buttons)

    # Кнопка возврата
    keyboard.append([InlineKeyboardButton(text="🏠 В меню статистики", callback_data="back_to_stats")])

    reply_markup = InlineKeyboardMarkup(inline_keyboard=keyboard)

    # Отправляем или редактируем сообщение
    if edit_message:
        try:
            await edit_message.edit_text(text, reply_markup=reply_markup)
        except Exception as e:
            logger.error(f"Ошибка при редактировании сообщения: {e}")
            # Если не удалось отредактировать, отправляем новое
            await message.answer(text, reply_markup=reply_markup)
    else:
        await message.answer(text, reply_markup=reply_markup)


async def show_store_summary(message: Message, user_id: int, store_name: str, store_data: dict = None,
                             edit_message: Message = None):
    """Показывает итоговую статистику магазина"""

    if user_id not in user_data_store:
        await message.answer("❌ Данные устарели. Запросите статистику заново.")
        return

    if not store_data:
        store_data = user_data_store[user_id]["store_data"].get(store_name)
        if not store_data:
            await message.answer(f"❌ Данные для магазина '{store_name}' не найдены.")
            return

    # Извлекаем данные из комбинированной статистики
    funnel_stats = store_data.get("funnel_stats", {})
    recommended_stats = store_data.get("recommended_stats", {})

    # Форматируем итоговые суммы
    total_order_sum = funnel_stats.get("total_order_sum", 0)
    total_buyout_sum = recommended_stats.get("total_buyout_sum", 0)

    total_order_sum_formatted = f"{total_order_sum:,.2f} ₽".replace(",", " ").replace(".", ",")
    total_buyout_sum_formatted = f"{total_buyout_sum:,.2f} ₽".replace(",", " ").replace(".", ",")

    # Рассчитываем процент выкупа
    total_orders = funnel_stats.get("total_orders", 0)
    total_buyouts = recommended_stats.get("total_buyouts", 0)

    if total_orders > 0:
        buyout_percent = (total_buyouts / total_orders) * 100
    else:
        buyout_percent = 0

    # Определяем текущий индекс магазина в списке
    stores_order = user_data_store[user_id]["stores_order"]
    current_index = stores_order.index(store_name) if store_name in stores_order else -1
    total_stores = len(stores_order)

    # Формируем текст
    text = f"<b>🏪 {store_name}</b>\n\n"

    text += "<b>ИТОГО ПО МАГАЗИНУ</b>\n\n"

    # Блок с заказами
    text += f"Заказов: <b>{total_orders:,} шт.</b> на <b>{total_order_sum_formatted}</b>\n"

    # Блок с выкупами
    text += f"Выкупов: <b>{total_buyouts:,} шт.</b> на <b>{total_buyout_sum_formatted}</b>\n"

    # Общая статистика
    text += f"Всего товаров: {funnel_stats.get('total_products', 0):,}\n"
    text += f"Всего просмотров: {store_data.get('total_views', 0):,}\n"
    text += f"Конверсия в корзину: {store_data.get('overall_cart_conversion', 0):.1f}%\n"
    text += f"Конверсия в заказ: {store_data.get('overall_order_conversion', 0):.1f}%\n\n"

    # Добавляем информацию о магазине в конец сообщения
    text += f"Магазин {current_index + 1}/{total_stores}"

    # Создаем клавиатуру
    keyboard = []

    # Кнопки навигации между магазинами
    nav_buttons = []
    if current_index > 0:
        prev_store = stores_order[current_index - 1]
        nav_buttons.append(InlineKeyboardButton(text="⏪ Пред. магазин", callback_data=f"store:{prev_store}:1"))

    # Кнопки действий
    action_buttons = []
    if store_data.get("has_activity", False):
        action_buttons.append(InlineKeyboardButton(text="📦 К товарам", callback_data=f"store:{store_name}:1"))

    if current_index >= 0 and current_index < total_stores - 1:
        next_store = stores_order[current_index + 1]
        nav_buttons.append(InlineKeyboardButton(text="След. магазин ⏩", callback_data=f"store:{next_store}:1"))

    if nav_buttons:
        keyboard.append(nav_buttons)

    if action_buttons:
        keyboard.append(action_buttons)

    # Кнопка возврата
    keyboard.append([InlineKeyboardButton(text="🏠 В меню статистики", callback_data="back_to_stats")])

    reply_markup = InlineKeyboardMarkup(inline_keyboard=keyboard)

    # Отправляем или редактируем сообщение
    if edit_message:
        try:
            await edit_message.edit_text(text, reply_markup=reply_markup)
        except Exception as e:
            logger.error(f"Ошибка при редактировании сообщения: {e}")
            await message.answer(text, reply_markup=reply_markup)
    else:
        await message.answer(text, reply_markup=reply_markup)


async def show_error_message(message: Message, user_id: int, store_name: str, store_data: dict,
                             edit_message: Message = None):
    """Показывает сообщение об ошибке для магазина"""

    error_message = store_data.get("error_message", "Неизвестная ошибка")
    display_error = store_data.get("display_error", "Ошибка подключения")

    # Определяем текущий индекс магазина в списке
    stores_order = user_data_store[user_id]["stores_order"]
    current_index = stores_order.index(store_name) if store_name in stores_order else -1
    total_stores = len(stores_order)

    text = f"<b>🏪 {store_name}</b>\n"
    text += f"Магазин {current_index + 1}/{total_stores}\n\n"
    text += f"<b>ОШИБКА:</b> {display_error}\n"
    text += f"<i>Детали: {error_message[:100]}...</i>\n\n"

    # Создаем клавиатуру
    keyboard = []

    # Кнопки навигации между магазинами
    nav_buttons = []
    if current_index > 0:
        prev_store = stores_order[current_index - 1]
        nav_buttons.append(InlineKeyboardButton(text="⏪ Пред. магазин", callback_data=f"store:{prev_store}:1"))

    if current_index >= 0 and current_index < total_stores - 1:
        next_store = stores_order[current_index + 1]
        nav_buttons.append(InlineKeyboardButton(text="След. магазин ⏩", callback_data=f"store:{next_store}:1"))

    if nav_buttons:
        keyboard.append(nav_buttons)

    # Кнопка возврата
    keyboard.append([InlineKeyboardButton(text="🏠 В меню статистики", callback_data="back_to_stats")])

    reply_markup = InlineKeyboardMarkup(inline_keyboard=keyboard)

    # Отправляем или редактируем сообщение
    if edit_message:
        try:
            await edit_message.edit_text(text, reply_markup=reply_markup)
        except Exception as e:
            logger.error(f"Ошибка при редактировании сообщения: {e}")
            await message.answer(text, reply_markup=reply_markup)
    else:
        await message.answer(text, reply_markup=reply_markup)


@yesterday_product_statistics_router.callback_query(F.data.startswith("page:"))
async def handle_page_navigation(callback: CallbackQuery):
    """Обработка перехода по страницам"""

    await callback.answer()

    try:
        _, store_name, page_str = callback.data.split(":")
        page = int(page_str)
        user_id = callback.from_user.id

        # Показываем указанную страницу с замещением текущего сообщения
        await show_store_page(callback.message, user_id, store_name, page, callback.message)
    except Exception as e:
        logger.error(f"Ошибка при обработке навигации по страницам: {e}")
        await callback.answer("❌ Ошибка при переключении страницы")


@yesterday_product_statistics_router.callback_query(F.data.startswith("store:"))
async def handle_store_navigation(callback: CallbackQuery):
    """Обработка перехода между магазинами"""

    await callback.answer()

    try:
        _, store_name, page_str = callback.data.split(":")
        page = int(page_str)
        user_id = callback.from_user.id

        store_data = user_data_store.get(user_id, {}).get("store_data", {}).get(store_name)

        if not store_data:
            await callback.answer("❌ Данные магазина не найдены")
            return

        if store_data.get("error", False):
            # Показываем ошибку
            await show_error_message(callback.message, user_id, store_name, store_data, callback.message)
        elif store_data.get("has_activity", False):
            # Показываем страницу с товарами
            await show_store_page(callback.message, user_id, store_name, page, callback.message)
        else:
            # Показываем итоговую статистику
            await show_store_summary(callback.message, user_id, store_name, store_data, callback.message)

    except Exception as e:
        logger.error(f"Ошибка при обработке навигации по магазинам: {e}")
        await callback.answer("❌ Ошибка при переключении магазина")


@yesterday_product_statistics_router.callback_query(F.data.startswith("summary:"))
async def handle_summary_view(callback: CallbackQuery):
    """Обработка просмотра итоговой статистики магазина"""

    await callback.answer()

    try:
        _, store_name = callback.data.split(":")
        user_id = callback.from_user.id

        store_data = user_data_store.get(user_id, {}).get("store_data", {}).get(store_name)

        if not store_data:
            await callback.answer("❌ Данные магазина не найдены")
            return

        if store_data.get("error", False):
            await callback.answer("❌ Для этого магазина есть только информация об ошибке")
            return

        # Показываем итоговую статистику с замещением текущего сообщения
        await show_store_summary(callback.message, user_id, store_name, store_data, callback.message)

    except Exception as e:
        logger.error(f"Ошибка при обработке просмотра итогов: {e}")
        await callback.answer("❌ Ошибка при отображении статистики")


@yesterday_product_statistics_router.callback_query(F.data == "back_to_stats")
async def handle_back_to_stats(callback: CallbackQuery):
    """Возврат в меню статистики"""

    await callback.answer()

    # Очищаем временные данные пользователя
    user_id = callback.from_user.id
    if user_id in user_data_store:
        del user_data_store[user_id]

    await callback.message.answer(
        "📊 Вы вернулись в меню статистики",
        reply_markup=get_stats_keyboard()
    )


# Обработчики для старых функций (для совместимости)
async def send_no_activity_store_stats(callback: CallbackQuery, account_name: str,
                                       funnel_stats: dict, sales_stats: dict, recommended_stats: dict,
                                       detailed_stats: dict):
    """Отправляет статистику для магазина без активности товаров"""

    total_order_sum = funnel_stats.get("total_order_sum", 0)
    total_order_sum_formatted = f"{total_order_sum:,.2f} ₽".replace(",", " ").replace(".", ",")

    total_buyout_sum = recommended_stats.get("total_buyout_sum", 0)
    total_buyout_sum_formatted = f"{total_buyout_sum:,.2f} ₽".replace(",", " ").replace(".", ",")

    await callback.message.answer(
        f"<b>🏪 {account_name}</b>\n\n"
        f"Нет активных товаров за этот день\n\n"
        f"<b>📊 ИТОГО ПО МАГАЗИНУ:</b>\n"
        f"• Заказов: {funnel_stats.get('total_orders', 0):,} шт. на {total_order_sum_formatted}\n"
        f"• Выкупов: {recommended_stats.get('total_buyouts', 0):,} шт. на {total_buyout_sum_formatted}\n\n"
        f"<i>Детали из API:</i>\n"
        f"• Всего товаров: {funnel_stats.get('total_products', 0):,}\n"
        f"• Просмотров: {detailed_stats.get('total_views', 0):,}\n"
        f"• В корзину: {detailed_stats.get('total_carts', 0):,}\n"
        f"• Источник выкупов: {sales_stats.get('data_source', 'N/A')}"
    )


async def send_basic_store_stats(callback: CallbackQuery, account_name: str,
                                 funnel_stats: dict, sales_stats: dict, recommended_stats: dict):
    """Отправляет базовую статистику без деталей по товарам"""

    total_order_sum = funnel_stats.get("total_order_sum", 0)
    total_order_sum_formatted = f"{total_order_sum:,.2f} ₽".replace(",", " ").replace(".", ",")

    total_buyout_sum = recommended_stats.get("total_buyout_sum", 0)
    total_buyout_sum_formatted = f"{total_buyout_sum:,.2f} ₽".replace(",", " ").replace(".", ",")

    await callback.message.answer(
        f"<b>🏪 {account_name}</b>\n\n"
        f"<b>📊 ОБЩАЯ СТАТИСТИКА:</b>\n"
        f"• Заказов: {funnel_stats.get('total_orders', 0):,} шт. на {total_order_sum_formatted}\n"
        f"• Выкупов: {recommended_stats.get('total_buyouts', 0):,} шт. на {total_buyout_sum_formatted}\n\n"
        f"<i>Детали:</i>\n"
        f"• Всего товаров: {funnel_stats.get('total_products', 0):,}\n"
        f"• Товаров с продажами: {funnel_stats.get('products_with_sales', 0):,}\n"
        f"• Источник выкупов: {sales_stats.get('data_source', 'N/A')}\n"
        f"<i>Не удалось получить детальные данные по товарам</i>"
    )


async def send_no_orders_store_stats(callback: CallbackQuery, account_name: str,
                                     funnel_stats: dict, sales_stats: dict, recommended_stats: dict):
    """Отправляет статистику для магазина без заказов и выкупов"""

    await callback.message.answer(
        f"<b>🏪 {account_name}</b>\n\n"
        f"Нет заказов и выкупов за этот день\n\n"
        f"<i>Статистика:</i>\n"
        f"• Заказов: {funnel_stats.get('total_orders', 0):,}\n"
        f"• Выкупов: {recommended_stats.get('total_buyouts', 0):,}\n"
        f"• Источник данных: {sales_stats.get('data_source', 'N/A')}"
    )















# handlers/yesterday_product_statistics_handlers.py
# import asyncio
# import logging
# from datetime import datetime, timedelta
# from aiogram import Router, F
# from aiogram.types import CallbackQuery
# from sqlalchemy.ext.asyncio import AsyncSession
# from database.account_manager import AccountManager
# from database.product_manager import ProductManager
# from functions.yesterday_product_statistics import YesterdayProductStatistics
# from keyboards.statistics_kb import get_stats_keyboard
#
# logger = logging.getLogger(__name__)
#
# yesterday_product_statistics_router = Router()
#
#
# @yesterday_product_statistics_router.callback_query(F.data == "yesterday_stats")
# async def handle_yesterday_stats(callback: CallbackQuery, session: AsyncSession):
#     """Показать детальную статистику по товарам за вчера для всех магазинов"""
#
#     await callback.answer()
#
#     logger.info("Получение статистики за вчера")
#
#     try:
#         loading_msg = await callback.message.answer(
#             "Получение статистики по товарам за вчера..."
#         )
#
#         account_manager = AccountManager(session)
#         all_accounts = await account_manager.get_all_accounts()
#
#         if not all_accounts:
#             await loading_msg.delete()
#             await callback.message.answer(
#                 "Нет добавленных магазинов",
#                 reply_markup=get_stats_keyboard()
#             )
#             return
#
#         logger.info(f"Найдено магазинов для обработки: {len(all_accounts)}")
#
#         successful_accounts = 0
#
#         # Получаем дату вчерашнего дня
#         yesterday_date_obj = datetime.now() - timedelta(days=1)
#         date_str = yesterday_date_obj.strftime("%d.%m.%Y")
#         days = ["Понедельник", "Вторник", "Среда", "Четверг", "Пятница", "Суббота", "Воскресенье"]
#         day_name = days[yesterday_date_obj.weekday()]
#
#         # Заголовок статистики
#         await loading_msg.delete()
#
#         header_text = (f"<b>📊 СТАТИСТИКА ЗА ВЧЕРА</b>\n{date_str} ({day_name})\n"
#                        f"Всего магазинов: {len(all_accounts)}\n\n"
#                        f"<i>(Только товары с заказами)</i>")
#         await callback.message.answer(header_text)
#
#         # Обрабатываем КАЖДЫЙ магазин отдельно
#         for account_index, account in enumerate(all_accounts, 1):
#             account_name = account.account_name or f"Магазин {account.id}"
#             logger.info(f"[{account_index}/{len(all_accounts)}] Обрабатываю магазин: {account_name}")
#
#             try:
#                 # Получаем комбинированную статистику для текущего магазина
#                 yesterday_stats = YesterdayProductStatistics(account.api_key)
#                 combined_stats = await yesterday_stats.get_combined_yesterday_stats()
#
#                 # Извлекаем данные из комбинированной статистики
#                 funnel_stats = combined_stats.get("funnel_stats", {})
#                 sales_stats = combined_stats.get("sales_stats", {})
#                 recommended_stats = combined_stats.get("recommended_stats", {})
#
#                 logger.info(f"[{account_name}] Товаров: {funnel_stats.get('total_products', 0)}")
#                 logger.info(f"[{account_name}] Заказов: {funnel_stats.get('total_orders', 0)}")
#                 logger.info(
#                     f"[{account_name}] Выкупов: {recommended_stats.get('total_buyouts', 0)} шт. на {recommended_stats.get('total_buyout_sum', 0):.2f} руб.")
#
#                 # Получаем товары из воронки продаж для сохранения в БД
#                 # (предполагается, что функция get_yesterday_product_stats() все еще доступна)
#                 try:
#                     # Получаем детальные данные по товарам для сохранения
#                     stats_obj = YesterdayProductStatistics(account.api_key)
#                     detailed_stats = await stats_obj.get_yesterday_product_stats()
#
#                     # Сохраняем товары в БД
#                     product_manager = ProductManager(session)
#                     saved_products_count = 0
#                     all_products_for_save = detailed_stats.get("all_products", [])
#
#                     for product_data in all_products_for_save:
#                         try:
#                             article = product_data.get('article')
#                             if article:
#                                 product = await product_manager.get_or_create_product(
#                                     seller_account_id=account.id,
#                                     supplier_article=article
#                                 )
#                                 saved_products_count += 1
#
#                                 title = product_data.get('title')
#                                 if title and not product.custom_name:
#                                     short_title = title[:100] if len(title) > 100 else title
#                                     await product_manager.update_custom_name(
#                                         seller_account_id=account.id,
#                                         supplier_article=article,
#                                         custom_name=short_title
#                                     )
#                         except Exception as e:
#                             logger.error(f"Ошибка при сохранении товара: {e}")
#
#                     logger.info(f"[{account_name}] Сохранено товаров: {saved_products_count}")
#
#                 except Exception as e:
#                     logger.error(f"[{account_name}] Ошибка при получении детальных данных: {e}")
#
#                 # Получаем кастомные названия из БД
#                 product_manager = ProductManager(session)
#                 custom_names = await product_manager.get_custom_names_dict(account.id)
#
#                 # Формируем сообщение для магазина
#                 if funnel_stats.get("total_orders", 0) > 0 or recommended_stats.get("total_buyouts", 0) > 0:
#                     # Получаем товары с заказами из детальной статистики
#                     try:
#                         stats_obj = YesterdayProductStatistics(account.api_key)
#                         detailed_stats = await stats_obj.get_yesterday_product_stats()
#                         products_with_orders = detailed_stats.get("products", [])
#
#                         # Фильтруем только товары с активностью
#                         products_with_activity = [p for p in products_with_orders if
#                                                   p.get('orders', 0) > 0 or p.get('buyouts', 0) > 0]
#
#                         if products_with_activity:
#                             # Объединяем данные для отправки
#                             combined_data = {
#                                 "funnel_stats": funnel_stats,
#                                 "sales_stats": sales_stats,
#                                 "recommended_stats": recommended_stats,
#                                 "total_views": detailed_stats.get("total_views", 0),
#                                 "total_carts": detailed_stats.get("total_carts", 0),
#                                 "overall_cart_conversion": detailed_stats.get("overall_cart_conversion", 0),
#                                 "overall_order_conversion": detailed_stats.get("overall_order_conversion", 0)
#                             }
#
#                             # Разбиваем на части и отправляем
#                             await send_store_statistics_parts(
#                                 callback,
#                                 account_name,
#                                 products_with_activity,
#                                 custom_names,
#                                 combined_data
#                             )
#
#                             successful_accounts += 1
#                         else:
#                             # Магазин без активности товаров
#                             await send_no_activity_store_stats(
#                                 callback,
#                                 account_name,
#                                 funnel_stats,
#                                 sales_stats,
#                                 recommended_stats,
#                                 detailed_stats
#                             )
#
#                     except Exception as e:
#                         logger.error(f"[{account_name}] Ошибка при получении детальной статистики: {e}")
#                         # Отправляем общую статистику без деталей по товарам
#                         await send_basic_store_stats(
#                             callback,
#                             account_name,
#                             funnel_stats,
#                             sales_stats,
#                             recommended_stats
#                         )
#
#                 else:
#                     # Магазин без заказов и выкупов
#                     await send_no_orders_store_stats(
#                         callback,
#                         account_name,
#                         funnel_stats,
#                         sales_stats,
#                         recommended_stats
#                     )
#
#             except Exception as e:
#                 error_message = str(e)
#                 logger.error(f"[{account_name}] Ошибка при получении статистики: {error_message}")
#
#                 if "Неверный API ключ" in error_message:
#                     display_error = "Неверный API ключ"
#                 elif "Превышен лимит запросов" in error_message:
#                     display_error = "Превышен лимит запросов API"
#                 elif "Таймаут запроса" in error_message:
#                     display_error = "Таймаут запроса"
#                 else:
#                     display_error = "Ошибка подключения к API"
#
#                 await callback.message.answer(
#                     f"<b>🏪 {account_name}</b>\n"
#                     f"<b>Ошибка:</b> {display_error}\n"
#                     f"<i>Детали: {error_message[:100]}</i>"
#                 )
#
#                 # Задержка перед следующим магазином в случае ошибки
#                 await asyncio.sleep(5)
#
#             # Задержка между запросами к разным магазинам
#             if account_index < len(all_accounts):
#                 await asyncio.sleep(10)
#
#         # Финальное сообщение
#         await callback.message.answer(
#             f"<b>Обработка завершена</b>\n"
#             f"Успешно обработано: {successful_accounts} из {len(all_accounts)} магазинов",
#             reply_markup=get_stats_keyboard()
#         )
#
#         logger.info(f"Статистика успешно отправлена для {successful_accounts}/{len(all_accounts)} магазинов")
#
#     except Exception as e:
#         logger.error(f"Неожиданная ошибка при получении статистики за вчера: {e}")
#         try:
#             await loading_msg.delete()
#         except:
#             pass
#
#         await callback.message.answer(
#             "<b>Произошла непредвиденная ошибка</b>\n"
#             f"<i>Детали: {str(e)[:100]}</i>\n"
#             "Попробуйте позже.",
#             reply_markup=get_stats_keyboard()
#         )
#
#
# async def send_store_statistics_parts(callback: CallbackQuery, account_name: str,
#                                       products_with_activity: list, custom_names: dict, stats: dict):
#     """Разбивает статистику магазина на части и отправляет отдельными сообщениями"""
#
#     # Максимальное количество товаров в одном сообщении (с HTML тегами нужно меньше)
#     MAX_PRODUCTS_PER_MESSAGE = 8
#
#     # Извлекаем данные из комбинированной статистики
#     funnel_stats = stats.get("funnel_stats", {})
#     recommended_stats = stats.get("recommended_stats", {})
#
#     # Форматируем итоговые суммы
#     total_order_sum = funnel_stats.get("total_order_sum", 0)
#     total_buyout_sum = recommended_stats.get("total_buyout_sum", 0)
#
#     total_order_sum_formatted = f"{total_order_sum:,.2f} ₽".replace(",", " ").replace(".", ",")
#     total_buyout_sum_formatted = f"{total_buyout_sum:,.2f} ₽".replace(",", " ").replace(".", ",")
#
#     # Рассчитываем процент выкупа
#     total_orders = funnel_stats.get("total_orders", 0)
#     total_buyouts = recommended_stats.get("total_buyouts", 0)
#
#     if total_orders > 0:
#         buyout_percent = (total_buyouts / total_orders) * 100
#     else:
#         buyout_percent = 0
#
#     # Отправляем заголовок магазина
#     await callback.message.answer(f"<b>🏪 {account_name}</b>")
#
#     # Разбиваем товары на части
#     total_products = len(products_with_activity)
#
#     for part_num, chunk_start in enumerate(range(0, total_products, MAX_PRODUCTS_PER_MESSAGE)):
#         chunk_end = min(chunk_start + MAX_PRODUCTS_PER_MESSAGE, total_products)
#         chunk = products_with_activity[chunk_start:chunk_end]
#
#         # Формируем часть сообщения
#         part_text = ""
#
#         # Если это первая часть и товаров много, добавляем информацию
#         if part_num == 0 and total_products > MAX_PRODUCTS_PER_MESSAGE:
#             part_text += f"<i>(товары 1-{MAX_PRODUCTS_PER_MESSAGE} из {total_products})</i>\n\n"
#
#         # Добавляем товары из текущего чанка
#         for i, product in enumerate(chunk, chunk_start + 1):
#             # Берем кастомное название из БД, если есть, иначе название из API
#             article = product.get('article', '')
#             display_name = custom_names.get(article)
#             if not display_name:
#                 display_name = product.get('title', '')
#
#             # Форматируем числа
#             views_formatted = f"{product.get('views', 0):,}"
#             carts_formatted = f"{product.get('carts', 0):,}"
#             orders_formatted = f"{product.get('orders', 0):,}"
#             order_sum_formatted = f"{product.get('order_sum', 0):,.2f} ₽".replace(",", " ").replace(".", ",")
#
#             # Выкупы могут быть не в данных товара, используем 0 как значение по умолчанию
#             buyouts = product.get('buyouts', 0)
#             buyout_sum = product.get('buyout_sum', 0)
#
#             buyouts_formatted = f"{buyouts:,}"
#             buyout_sum_formatted = f"{buyout_sum:,.2f} ₽".replace(",", " ").replace(".", ",")
#
#             # Рассчитываем процент выкупа для товара
#             if product.get('orders', 0) > 0:
#                 product_buyout_percent = (buyouts / product.get('orders', 1)) * 100
#                 buyout_percent_formatted = f"{product_buyout_percent:.1f}%"
#             else:
#                 buyout_percent_formatted = "0%"
#
#             # Добавляем товар с выкупами
#             part_text += f"<b>{i}. {display_name}</b>\n"
#             part_text += f"   • Артикул: {article}\n"
#             part_text += f"   • Просмотры: {views_formatted}\n"
#             part_text += f"   • В корзине: {carts_formatted}\n"
#             part_text += f"   • Конверсия в корзину: {product.get('conversion_to_cart', 0):.1f}%\n"
#             part_text += f"   • Конверсия в заказ: {product.get('conversion_to_order', 0):.1f}%\n"
#             part_text += f"   • <b>Заказы: {orders_formatted} шт. на {order_sum_formatted}</b>\n"
#             part_text += f"   • <b>Выкупы: {buyouts_formatted} шт. на {buyout_sum_formatted}</b>\n\n"
#
#         # Если это не последняя часть, добавляем информацию о продолжении
#         if chunk_end < total_products:
#             next_chunk_start = chunk_end
#             next_chunk_end = min(next_chunk_start + MAX_PRODUCTS_PER_MESSAGE, total_products)
#             part_text += f"<i>... продолжение ({next_chunk_start + 1}-{next_chunk_end}) ...</i>\n"
#
#         # Отправляем часть сообщения
#         await callback.message.answer(part_text)
#
#         # Небольшая задержка между сообщениями
#         await asyncio.sleep(0.3)
#
#     # Создаем итоговую часть с ВЫКУПАМИ
#     final_part = "<b>📊 ИТОГО ПО МАГАЗИНУ</b>\n"
#     final_part += "═" * 30 + "\n"
#
#     # Блок с заказами
#     final_part += f"<b>📈 ЗАКАЗЫ:</b>\n"
#     final_part += f"   • Заказов: <b>{total_orders:,} шт.</b>\n"
#     final_part += f"   • Сумма заказов: <b>{total_order_sum_formatted}</b>\n\n"
#
#     # Блок с выкупами
#     final_part += f"<b>✅ ВЫКУПЫ:</b>\n"
#     final_part += f"   • Выкупов: <b>{total_buyouts:,} шт.</b>\n"
#     final_part += f"   • Сумма выкупов: <b>{total_buyout_sum_formatted}</b>\n"
#     final_part += f"   • Процент выкупа: <b>{buyout_percent:.1f}%</b>\n\n"
#
#     # Общая статистика
#     final_part += f"<b>📋 ОБЩАЯ СТАТИСТИКА:</b>\n"
#     final_part += f"   • Всего товаров: {funnel_stats.get('total_products', 0):,}\n"
#     final_part += f"   • Товаров с продажами: {funnel_stats.get('products_with_sales', 0):,}\n"
#     final_part += f"   • Общее просмотров: {stats.get('total_views', 0):,}\n"
#     final_part += f"   • Конверсия в корзину: {stats.get('overall_cart_conversion', 0):.1f}%\n"
#     final_part += f"   • Конверсия в заказ: {stats.get('overall_order_conversion', 0):.1f}%\n"
#
#     # Отправляем итоговую часть
#     await callback.message.answer(final_part)
#
#
# async def send_no_activity_store_stats(callback: CallbackQuery, account_name: str,
#                                        funnel_stats: dict, sales_stats: dict, recommended_stats: dict,
#                                        detailed_stats: dict):
#     """Отправляет статистику для магазина без активности товаров"""
#
#     total_order_sum = funnel_stats.get("total_order_sum", 0)
#     total_order_sum_formatted = f"{total_order_sum:,.2f} ₽".replace(",", " ").replace(".", ",")
#
#     total_buyout_sum = recommended_stats.get("total_buyout_sum", 0)
#     total_buyout_sum_formatted = f"{total_buyout_sum:,.2f} ₽".replace(",", " ").replace(".", ",")
#
#     await callback.message.answer(
#         f"<b>🏪 {account_name}</b>\n\n"
#         f"Нет активных товаров за этот день\n\n"
#         f"<b>📊 ИТОГО ПО МАГАЗИНУ:</b>\n"
#         f"• Заказов: {funnel_stats.get('total_orders', 0):,} шт. на {total_order_sum_formatted}\n"
#         f"• Выкупов: {recommended_stats.get('total_buyouts', 0):,} шт. на {total_buyout_sum_formatted}\n\n"
#         f"<i>Детали из API:</i>\n"
#         f"• Всего товаров: {funnel_stats.get('total_products', 0):,}\n"
#         f"• Просмотров: {detailed_stats.get('total_views', 0):,}\n"
#         f"• В корзину: {detailed_stats.get('total_carts', 0):,}\n"
#         f"• Источник выкупов: {sales_stats.get('data_source', 'N/A')}"
#     )
#
#
# async def send_basic_store_stats(callback: CallbackQuery, account_name: str,
#                                  funnel_stats: dict, sales_stats: dict, recommended_stats: dict):
#     """Отправляет базовую статистику без деталей по товарам"""
#
#     total_order_sum = funnel_stats.get("total_order_sum", 0)
#     total_order_sum_formatted = f"{total_order_sum:,.2f} ₽".replace(",", " ").replace(".", ",")
#
#     total_buyout_sum = recommended_stats.get("total_buyout_sum", 0)
#     total_buyout_sum_formatted = f"{total_buyout_sum:,.2f} ₽".replace(",", " ").replace(".", ",")
#
#     await callback.message.answer(
#         f"<b>🏪 {account_name}</b>\n\n"
#         f"<b>📊 ОБЩАЯ СТАТИСТИКА:</b>\n"
#         f"• Заказов: {funnel_stats.get('total_orders', 0):,} шт. на {total_order_sum_formatted}\n"
#         f"• Выкупов: {recommended_stats.get('total_buyouts', 0):,} шт. на {total_buyout_sum_formatted}\n\n"
#         f"<i>Детали:</i>\n"
#         f"• Всего товаров: {funnel_stats.get('total_products', 0):,}\n"
#         f"• Товаров с продажами: {funnel_stats.get('products_with_sales', 0):,}\n"
#         f"• Источник выкупов: {sales_stats.get('data_source', 'N/A')}\n"
#         f"<i>Не удалось получить детальные данные по товарам</i>"
#     )
#
#
# async def send_no_orders_store_stats(callback: CallbackQuery, account_name: str,
#                                      funnel_stats: dict, sales_stats: dict, recommended_stats: dict):
#     """Отправляет статистику для магазина без заказов и выкупов"""
#
#     await callback.message.answer(
#         f"<b>🏪 {account_name}</b>\n\n"
#         f"Нет заказов и выкупов за этот день\n\n"
#         f"<i>Статистика:</i>\n"
#         f"• Всего товаров: {funnel_stats.get('total_products', 0):,}\n"
#         f"• Товаров с продажами: {funnel_stats.get('products_with_sales', 0):,}\n"
#         f"• Заказов: {funnel_stats.get('total_orders', 0):,}\n"
#         f"• Выкупов: {recommended_stats.get('total_buyouts', 0):,}\n"
#         f"• Источник данных: {sales_stats.get('data_source', 'N/A')}"
#     )