# handlers/yesterday_product_statistics_handlers.py
import asyncio
import logging
from datetime import datetime, timedelta
from aiogram import Router, F
from aiogram.types import CallbackQuery, Message, InlineKeyboardMarkup, InlineKeyboardButton
from sqlalchemy.ext.asyncio import AsyncSession
from database.account_manager import AccountManager
from database.product_manager import ProductManager
from functions.yesterday_product_statistics import YesterdayProductStatistics
from keyboards.statistics_kb import get_stats_keyboard
from storage.yesterday_statistics_storage import get_user_data, set_user_data

logger = logging.getLogger(__name__)

yesterday_product_statistics_router = Router()


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
        user_data = {
            "account_index": 0,
            "store_index": 0,
            "current_page": {},
            "store_data": {},
            "stores_order": [],  # Порядок магазинов для навигации
            "total_accounts": len(all_accounts),
            "date_str": date_str,
            "day_name": day_name,
            "successful_accounts": 0,
            "failed_accounts": 0,
            "is_auto_report": False  # Это ручной запрос
        }

        set_user_data(user_id, user_data, is_auto_report=False)

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
                    "total_views": detailed_stats.get("total_views", 0) if detailed_stats else 0,
                    "total_carts": detailed_stats.get("total_carts", 0) if detailed_stats else 0,
                    "overall_cart_conversion": detailed_stats.get("overall_cart_conversion",
                                                                  0) if detailed_stats else 0,
                    "overall_order_conversion": detailed_stats.get("overall_order_conversion",
                                                                   0) if detailed_stats else 0,
                    "has_activity": len(products_with_activity) > 0
                }

                user_data["store_data"][account_name] = store_data
                stores_order.append(account_name)

                # Обновляем счетчики
                if funnel_stats.get("total_orders", 0) > 0 or recommended_stats.get("total_buyouts", 0) > 0:
                    successful_accounts += 1
                    user_data["successful_accounts"] = successful_accounts
                else:
                    failed_accounts += 1
                    user_data["failed_accounts"] = failed_accounts

            except Exception as e:
                error_message = str(e)
                logger.error(f"[{account_name}] Ошибка при получении статистики: {error_message}")
                failed_accounts += 1
                user_data["failed_accounts"] = failed_accounts

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

                user_data["store_data"][account_name] = error_data
                stores_order.append(account_name)

            # Задержка между запросами к разным магазинам
            if account_index < len(all_accounts):
                await asyncio.sleep(5)

        # Сохраняем порядок магазинов
        user_data["stores_order"] = stores_order
        user_data["successful_accounts"] = successful_accounts
        user_data["failed_accounts"] = failed_accounts

        set_user_data(user_id, user_data, is_auto_report=False)

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
        user_data["header_message_id"] = header_msg.message_id
        set_user_data(user_id, user_data, is_auto_report=False)

        # В ИЗМЕНЕННОМ ВАРИАНТЕ: ПОКАЗЫВАЕМ СНАЧАЛА ИТОГИ МАГАЗИНА
        if stores_order:
            first_store = stores_order[0]
            store_data = user_data["store_data"].get(first_store)

            if store_data.get("error", False):
                # Показываем ошибку
                await show_error_message(callback.message, user_id, first_store, store_data, is_auto_report=False)
            else:
                # ПОКАЗЫВАЕМ СНАЧАЛА ИТОГОВУЮ СТАТИСТИКУ МАГАЗИНА
                await show_store_summary(callback.message, user_id, first_store, store_data, is_auto_report=False)
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


async def show_store_page(message: Message, user_id: int, store_name: str, page: int = 1,
                          edit_message: Message = None, is_auto_report: bool = False):
    """Показывает страницу с товарами магазина (с замещением предыдущей)"""

    # Используем бота из объекта сообщения или callback
    bot = message.bot if message else (edit_message.bot if edit_message else None)
    if not bot:
        logger.error("Не удалось получить экземпляр бота в show_store_page")
        return

    user_data = get_user_data(user_id, is_auto_report)
    if not user_data:
        await bot.send_message(user_id, "❌ Данные устарели. Запросите статистику заново.")
        return

    store_data = user_data.get("store_data", {}).get(store_name)
    if not store_data or store_data.get("error", False):
        await bot.send_message(user_id, f"❌ Данные для магазина '{store_name}' не найдены или содержат ошибку.")
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
    user_data["current_page"][store_name] = page
    set_user_data(user_id, user_data, is_auto_report)

    # Определяем текущий индекс магазина в списке
    stores_order = user_data.get("stores_order", [])
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
        text += f"Заказы: <b>{orders_formatted}</b> шт. на <b>{order_sum_formatted}</b>\n"
        text += f"<i>Просмотров: {views_formatted}  |  В корзине: {carts_formatted}</i>\n"
        text += f"<i>Конверсия: в корзину {product.get('conversion_to_cart', 0):.1f}%, в заказ: {product.get('conversion_to_order', 0):.1f}%</i>\n\n"


    # Добавляем информацию о странице в конец сообщения
    text += f"Страница {page}/{total_pages} | Товары {start_idx + 1}-{end_idx} из {total_products}\n"
    text += f"Магазин {current_index + 1}/{total_stores}"

    # Определяем префикс для callback-ов
    prefix = "auto_" if is_auto_report else ""

    # Создаем клавиатуру
    keyboard = []

    # Кнопки навигации по страницам (только влево-вправо)
    nav_buttons = []
    if page > 1:
        nav_buttons.append(InlineKeyboardButton(
            text="◀️ Назад",
            callback_data=f"{prefix}page:{store_name}:{page - 1}"
        ))

    if page < total_pages:
        nav_buttons.append(InlineKeyboardButton(
            text="Вперед ▶️",
            callback_data=f"{prefix}page:{store_name}:{page + 1}"
        ))

    if nav_buttons:
        keyboard.append(nav_buttons)

    # Кнопки навигации между магазинами
    store_nav_buttons = []
    if current_index > 0:
        prev_store = stores_order[current_index - 1]
        store_nav_buttons.append(InlineKeyboardButton(
            text="⏪ Пред. магазин",
            callback_data=f"{prefix}store:{prev_store}:1"
        ))

    # Кнопки действий
    action_buttons = []
    action_buttons.append(InlineKeyboardButton(
        text="📊 Назад к итогам",
        callback_data=f"{prefix}summary_back:{store_name}"
    ))

    if current_index >= 0 and current_index < total_stores - 1:
        next_store = stores_order[current_index + 1]
        store_nav_buttons.append(InlineKeyboardButton(
            text="След. магазин ⏩",
            callback_data=f"{prefix}store:{next_store}:1"
        ))

    if store_nav_buttons:
        keyboard.append(store_nav_buttons)

    if action_buttons:
        keyboard.append(action_buttons)

    reply_markup = InlineKeyboardMarkup(inline_keyboard=keyboard)

    # Отправляем или редактируем сообщение
    if edit_message:
        try:
            await edit_message.edit_text(text, reply_markup=reply_markup)
        except Exception as e:
            logger.error(f"Ошибка при редактировании сообщения: {e}")
            await bot.send_message(user_id, text, reply_markup=reply_markup)
    else:
        await bot.send_message(user_id, text, reply_markup=reply_markup)


async def show_store_summary(message: Message, user_id: int, store_name: str, store_data: dict = None,
                             edit_message: Message = None, is_auto_report: bool = False, bot=None):
    """Показывает итоговую статистику магазина на первом экране"""

    # Если бот передан как аргумент - используем его, иначе получаем из сообщения
    if not bot:
        bot = message.bot if message else (edit_message.bot if edit_message else None)

    if not bot:
        logger.error("Не удалось получить экземпляр бота в show_store_summary")
        return

    user_data = get_user_data(user_id, is_auto_report)
    if not user_data:
        await bot.send_message(user_id, "❌ Данные устарели. Запросите статистику заново.")
        return

    if not store_data:
        store_data = user_data.get("store_data", {}).get(store_name)
        if not store_data:
            await bot.send_message(user_id, f"❌ Данные для магазина '{store_name}' не найдены.")
            return

    # Извлекаем данные из комбинированной статистики
    funnel_stats = store_data.get("funnel_stats", {})
    recommended_stats = store_data.get("recommended_stats", {})

    # Форматируем итоговые суммы
    total_order_sum = funnel_stats.get("total_order_sum", 0)
    total_buyout_sum = recommended_stats.get("total_buyout_sum", 0)

    total_order_sum_formatted = f"{total_order_sum:,.2f} ₽".replace(",", " ").replace(".", ",")
    total_buyout_sum_formatted = f"{total_buyout_sum:,.2f} ₽".replace(",", " ").replace(".", ",")

    # Определяем текущий индекс магазина в списке
    stores_order = user_data.get("stores_order", [])
    current_index = stores_order.index(store_name) if store_name in stores_order else -1
    total_stores = len(stores_order)

    # Формируем текст
    text = f"<b>🏪 {store_name}</b>\n\n"

    text += "<b>ИТОГО ПО МАГАЗИНУ</b>\n\n"

    # Блок с заказами
    text += f"Заказов: <b>{funnel_stats.get('total_orders', 0):,} шт.</b> на <b>{total_order_sum_formatted}</b>\n"

    # Блок с выкупами
    text += f"Выкупов: <b>{recommended_stats.get('total_buyouts', 0):,} шт.</b> на <b>{total_buyout_sum_formatted}</b>\n"

    # Общая статистика
    text += f"Всего товаров: {funnel_stats.get('total_products', 0):,}\n"
    text += f"Всего просмотров: {store_data.get('total_views', 0):,}\n"
    text += f"Конверсия в корзину: {store_data.get('overall_cart_conversion', 0):.1f}%\n"
    text += f"Конверсия в заказ: {store_data.get('overall_order_conversion', 0):.1f}%\n\n"

    # Добавляем информацию о магазине в конец сообщения
    text += f"Магазин {current_index + 1}/{total_stores}"

    # Определяем префикс для callback-ов
    prefix = "auto_" if is_auto_report else ""

    # Создаем клавиатуру
    keyboard = []

    # Кнопки навигации между магазинами
    nav_buttons = []
    if current_index > 0:
        prev_store = stores_order[current_index - 1]
        nav_buttons.append(InlineKeyboardButton(
            text="⏪ Пред. магазин",
            callback_data=f"{prefix}store:{prev_store}:1"
        ))

    # Кнопки действий
    action_buttons = []
    if store_data.get("has_activity", False):
        action_buttons.append(InlineKeyboardButton(
            text="📦 К товарам",
            callback_data=f"{prefix}store_products:{store_name}:1"
        ))

    if current_index >= 0 and current_index < total_stores - 1:
        next_store = stores_order[current_index + 1]
        nav_buttons.append(InlineKeyboardButton(
            text="След. магазин ⏩",
            callback_data=f"{prefix}store:{next_store}:1"
        ))

    if nav_buttons:
        keyboard.append(nav_buttons)

    if action_buttons:
        keyboard.append(action_buttons)

    reply_markup = InlineKeyboardMarkup(inline_keyboard=keyboard)

    # Отправляем или редактируем сообщение
    if edit_message:
        try:
            await edit_message.edit_text(text, reply_markup=reply_markup)
        except Exception as e:
            logger.error(f"Ошибка при редактировании сообщения: {e}")
            await bot.send_message(user_id, text, reply_markup=reply_markup)
    else:
        await bot.send_message(user_id, text, reply_markup=reply_markup)


async def show_error_message(message: Message, user_id: int, store_name: str, store_data: dict,
                             edit_message: Message = None, is_auto_report: bool = False, bot=None):
    """Показывает сообщение об ошибке для магазина"""

    # Если бот передан как аргумент - используем его, иначе получаем из сообщения
    if not bot:
        bot = message.bot if message else (edit_message.bot if edit_message else None)

    if not bot:
        logger.error("Не удалось получить экземпляр бота в show_error_message")
        return

    user_data = get_user_data(user_id, is_auto_report)
    if not user_data:
        await bot.send_message(user_id, "❌ Данные устарели. Запросите статистику заново.")
        return

    error_message = store_data.get("error_message", "Неизвестная ошибка")
    display_error = store_data.get("display_error", "Ошибка подключения")

    # Определяем текущий индекс магазина в списке
    stores_order = user_data.get("stores_order", [])
    current_index = stores_order.index(store_name) if store_name in stores_order else -1
    total_stores = len(stores_order)

    text = f"<b>🏪 {store_name}</b>\n"
    text += f"Магазин {current_index + 1}/{total_stores}\n\n"
    text += f"<b>ОШИБКА:</b> {display_error}\n"
    text += f"<i>Детали: {error_message[:100]}...</i>\n\n"

    # Определяем префикс для callback-ов
    prefix = "auto_" if is_auto_report else ""

    # Создаем клавиатуру
    keyboard = []

    # Кнопки навигации между магазинами
    nav_buttons = []
    if current_index > 0:
        prev_store = stores_order[current_index - 1]
        nav_buttons.append(InlineKeyboardButton(
            text="⏪ Пред. магазин",
            callback_data=f"{prefix}store:{prev_store}:1"
        ))

    if current_index >= 0 and current_index < total_stores - 1:
        next_store = stores_order[current_index + 1]
        nav_buttons.append(InlineKeyboardButton(
            text="След. магазин ⏩",
            callback_data=f"{prefix}store:{next_store}:1"
        ))

    if nav_buttons:
        keyboard.append(nav_buttons)

    reply_markup = InlineKeyboardMarkup(inline_keyboard=keyboard)

    # Отправляем или редактируем сообщение
    if edit_message:
        try:
            await edit_message.edit_text(text, reply_markup=reply_markup)
        except Exception as e:
            logger.error(f"Ошибка при редактировании сообщения: {e}")
            await bot.send_message(user_id, text, reply_markup=reply_markup)
    else:
        await bot.send_message(user_id, text, reply_markup=reply_markup)


# Общие обработчики callback-ов
async def handle_callback_navigation(callback: CallbackQuery, prefix: str = ""):
    """Общий обработчик навигации"""
    await callback.answer()

    try:
        data = callback.data.replace(prefix, "") if prefix else callback.data

        if data.startswith("page:"):
            _, store_name, page_str = data.split(":")
            page = int(page_str)
            user_id = callback.from_user.id
            is_auto_report = prefix == "auto_"

            # Используем bot из callback
            await show_store_page(callback.message, user_id, store_name, page,
                                  callback.message, is_auto_report)

        elif data.startswith("store:"):
            _, store_name, page_str = data.split(":")
            page = int(page_str)
            user_id = callback.from_user.id
            is_auto_report = prefix == "auto_"

            user_data = get_user_data(user_id, is_auto_report)
            store_data = user_data.get("store_data", {}).get(store_name) if user_data else None

            if not store_data:
                await callback.answer("❌ Данные магазина не найдены")
                return

            if store_data.get("error", False):
                await show_error_message(callback.message, user_id, store_name,
                                         store_data, callback.message, is_auto_report)
            else:
                await show_store_summary(callback.message, user_id, store_name,
                                         store_data, callback.message, is_auto_report)

        elif data.startswith("store_products:"):
            _, store_name, page_str = data.split(":")
            page = int(page_str)
            user_id = callback.from_user.id
            is_auto_report = prefix == "auto_"

            user_data = get_user_data(user_id, is_auto_report)
            store_data = user_data.get("store_data", {}).get(store_name) if user_data else None

            if not store_data:
                await callback.answer("❌ Данные магазина не найдены")
                return

            if store_data.get("error", False):
                await callback.answer("❌ Для этого магазина есть только информация об ошибке")
                return

            await show_store_page(callback.message, user_id, store_name, page,
                                  callback.message, is_auto_report)

        elif data.startswith("summary_back:"):
            _, store_name = data.split(":")
            user_id = callback.from_user.id
            is_auto_report = prefix == "auto_"

            user_data = get_user_data(user_id, is_auto_report)
            store_data = user_data.get("store_data", {}).get(store_name) if user_data else None

            if not store_data:
                await callback.answer("❌ Данные магазина не найдены")
                return

            if store_data.get("error", False):
                await callback.answer("❌ Для этого магазина есть только информация об ошибке")
                return

            await show_store_summary(callback.message, user_id, store_name,
                                     store_data, callback.message, is_auto_report)

    except Exception as e:
        logger.error(f"Ошибка при обработке навигации: {e}")
        await callback.answer("❌ Ошибка при обработке запроса")


# Обработчики для ручных запросов (без префикса)
@yesterday_product_statistics_router.callback_query(F.data.startswith("page:"))
async def handle_page_navigation(callback: CallbackQuery):
    """Обработка перехода по страницам товаров"""
    await handle_callback_navigation(callback, prefix="")


@yesterday_product_statistics_router.callback_query(F.data.startswith("store:"))
async def handle_store_navigation(callback: CallbackQuery):
    """Обработка перехода между магазинами (ПОКАЗЫВАЕТ ИТОГИ)"""
    await handle_callback_navigation(callback, prefix="")


@yesterday_product_statistics_router.callback_query(F.data.startswith("store_products:"))
async def handle_store_products_view(callback: CallbackQuery):
    """Обработка перехода к товарам магазина"""
    await handle_callback_navigation(callback, prefix="")


@yesterday_product_statistics_router.callback_query(F.data.startswith("summary_back:"))
async def handle_summary_back_view(callback: CallbackQuery):
    """Обработка возврата к итогам магазина из просмотра товаров"""
    await handle_callback_navigation(callback, prefix="")


# Обработчики для автоотчетов (с префиксом auto_)
@yesterday_product_statistics_router.callback_query(F.data.startswith("auto_page:"))
async def handle_auto_page_navigation(callback: CallbackQuery):
    """Обработка перехода по страницам товаров в автоотчетах"""
    await handle_callback_navigation(callback, prefix="auto_")


@yesterday_product_statistics_router.callback_query(F.data.startswith("auto_store:"))
async def handle_auto_store_navigation(callback: CallbackQuery):
    """Обработка перехода между магазинами в автоотчетах (ПОКАЗЫВАЕТ ИТОГИ)"""
    await handle_callback_navigation(callback, prefix="auto_")


@yesterday_product_statistics_router.callback_query(F.data.startswith("auto_store_products:"))
async def handle_auto_store_products_view(callback: CallbackQuery):
    """Обработка перехода к товарам магазина в автоотчетах"""
    await handle_callback_navigation(callback, prefix="auto_")


@yesterday_product_statistics_router.callback_query(F.data.startswith("auto_summary_back:"))
async def handle_auto_summary_back_view(callback: CallbackQuery):
    """Обработка возврата к итогам магазина из просмотра товаров в автоотчетах"""
    await handle_callback_navigation(callback, prefix="auto_")


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