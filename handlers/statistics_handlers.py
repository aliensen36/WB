# handlers/statistics_handlers.py
import asyncio
from aiogram import Router, F
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession
from database.account_manager import AccountManager
from database.product_manager import ProductManager
from functions.wb_api import WBAPI
from keyboards.main_kb import get_main_keyboard
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

statistics_router = Router()


@statistics_router.message(F.text == "📊 Статистика")
async def show_all_accounts_stats(message: Message, session: AsyncSession):
    """Показать статистику всех магазинов с ожиданием получения данных"""

    loading_msg = await message.answer(
        "📊 <b>Получение статистики...</b>\n\n"
        "🔄 Загружаем данные по всем магазинам...\n"
        "<i>Это может занять несколько минут при превышении лимитов</i>",
        reply_markup=get_main_keyboard()
    )

    try:
        account_manager = AccountManager(session)
        all_accounts = await account_manager.get_all_accounts()

        if not all_accounts:
            await loading_msg.delete()
            await message.answer(
                "❌ <b>Нет добавленных магазинов</b>\n\n"
                "Перейдите в настройки, чтобы добавить первый магазин.",
                reply_markup=get_main_keyboard()
            )
            return

        today = datetime.now().strftime("%d.%m.%Y")
        stats_text = f"📊 <b>Статистика всех магазинов</b>\n\n"
        stats_text += f"📅 За сегодня (<b>{today}</b>)\n\n"

        successful_accounts = 0
        failed_accounts = 0
        rate_limited_accounts = 0

        # Собираем статистику по каждому магазину с задержками
        for i, account in enumerate(all_accounts):
            account_display_name = account.account_name or f"Магазин {account.id}"

            try:
                # Задержка между запросами к разным аккаунтам
                if i > 0:
                    await asyncio.sleep(5)

                # Простое обновление прогресса (не чаще чем раз в 10 магазинов)
                if i % 3 == 0:  # Обновляем каждые 3 магазина
                    try:
                        await loading_msg.edit_text(
                            f"📊 <b>Получение статистики...</b>\n\n"
                            f"🔄 Обработано {i}/{len(all_accounts)} магазинов\n"
                            f"✅ Успешно: {successful_accounts}\n"
                            f"❌ Ошибки: {failed_accounts}"
                        )
                    except:
                        pass  # Игнорируем ошибки редактирования

                wb_api = WBAPI(account.api_key)
                stats = await wb_api.get_today_stats_for_message()

                orders_quantity = stats["orders"]["quantity"]
                orders_amount = stats["orders"]["amount"]
                sales_quantity = stats["sales"]["quantity"]
                sales_amount = stats["sales"]["amount"]

                formatted_orders_amount = f"{orders_amount:,.0f} ₽".replace(",", " ").replace(".", ",")
                formatted_sales_amount = f"{sales_amount:,.2f} ₽".replace(",", " ").replace(".", ",")

                stats_text += f"<b>{account_display_name}</b>\n"
                stats_text += f"🛒 Заказы: <b>{orders_quantity}</b> шт. на <b>{formatted_orders_amount}</b>\n"
                stats_text += f"📈 Выкупы: <b>{sales_quantity}</b> шт. на <b>{formatted_sales_amount}</b>\n\n"

                successful_accounts += 1

            except Exception as e:
                error_message = str(e)

                # Извлекаем только конкретную причину ошибки
                if "Неверный API ключ" in error_message:
                    display_error = "Неверный API ключ"
                elif "Превышен лимит запросов" in error_message:
                    display_error = "Превышен лимит запросов"
                    rate_limited_accounts += 1
                elif "Таймаут запроса" in error_message:
                    display_error = "Таймаут запроса"
                else:
                    display_error = "Ошибка подключения"

                stats_text += f"<b>{account_display_name}</b>\n"
                stats_text += f"❌ {display_error}\n\n"
                failed_accounts += 1

                logger.warning(f"Ошибка для {account_display_name}: {error_message}")

        # Финальное обновление прогресса
        try:
            await loading_msg.edit_text(
                f"📊 <b>Завершено!</b>\n\n"
                f"✅ Успешно: {successful_accounts}\n"
                f"❌ Ошибки: {failed_accounts}\n"
                f"📊 Формируем отчет..."
            )
            await asyncio.sleep(1)  # Даем пользователю увидеть финальный прогресс
        except:
            pass  # Игнорируем ошибки редактирования

        # Добавляем подсказку только если есть ошибки лимита
        if rate_limited_accounts > 0:
            stats_text += "💡 <i>Некоторые данные не получены из-за ограничений API. Попробуйте позже.</i>"

        await loading_msg.delete()
        await message.answer(stats_text, reply_markup=get_main_keyboard())

    except Exception as e:
        logger.error(f"Неожиданная ошибка: {e}")
        try:
            await loading_msg.delete()
        except:
            pass
        await message.answer(
            "❌ <b>Произошла непредвиденная ошибка</b>\n\n"
            "<i>Попробуйте позже</i>",
            reply_markup=get_main_keyboard()
        )


@statistics_router.message(F.text == "📦 Статистика по товарам")
async def show_product_statistics(message: Message, session: AsyncSession):
    """
    Показать детальную статистику по товарам за ВЧЕРАШНИЙ день
    Используем API воронки продаж (/api/analytics/v3/sales-funnel/products)
    """
    # Простое сообщение без редактирования
    initial_msg = await message.answer(
        "📊 <b>Собираем статистику по товарам за вчера...</b>\n"
        "🔄 Использую API воронки продаж...",
        reply_markup=get_main_keyboard()
    )

    try:
        from datetime import datetime, timedelta
        import json

        account_manager = AccountManager(session)
        all_accounts = await account_manager.get_all_accounts()

        if not all_accounts:
            await message.answer(
                "❌ <b>Нет добавленных магазинов</b>",
                reply_markup=get_main_keyboard()
            )
            return

        # Берем первый аккаунт из списка
        account = all_accounts[0]
        account_name = account.account_name or f"Магазин {account.id}"

        # Получаем дату вчера
        yesterday = datetime.now().date() - timedelta(days=1)
        yesterday_str = yesterday.strftime("%d.%m.%Y")
        yesterday_api_str = yesterday.strftime("%Y-%m-%d")

        # День недели на русском
        days = ["Понедельник", "Вторник", "Среда", "Четверг", "Пятница", "Суббота", "Воскресенье"]
        day_name = days[yesterday.weekday()]

        # Инициализируем сервисы
        product_manager = ProductManager(session)

        # Используем API воронки продаж вместо API заказов
        logger.info(f"🔄 Использую API воронки продаж за {yesterday_str}")

        # Создаем экземпляр извлекателя данных
        from wb_api_client.sales_funnel_yesterday import YesterdaySalesFunnelExtractor

        # Инициализируем с API токеном из аккаунта
        extractor = YesterdaySalesFunnelExtractor()
        # Переопределяем токен из аккаунта
        extractor.api_token = account.api_key
        extractor.headers = {
            "Authorization": f"Bearer {account.api_key}",
            "Content-Type": "application/json",
            "accept": "application/json"
        }

        # Получаем ВСЕ данные за вчерашний день с пагинацией
        all_data, date_str_dd_mm_yyyy, date_str_yyyy_mm_dd = extractor.extract_all_data(batch_size=500)

        # Если нет данных
        if not all_data:
            await message.answer(
                f"📭 <b>Нет данных за {yesterday_str}</b>\n\n"
                f"🏪 {account_name}\n"
                f"📅 {day_name}\n\n"
                f"<i>API воронки продаж не вернул данные за этот день</i>\n"
                f"<i>Эндпоинт: /api/analytics/v3/sales-funnel/products</i>",
                reply_markup=get_main_keyboard()
            )
            return

        logger.info(f"📦 Получено товаров за {yesterday_str}: {len(all_data)}")

        # Обрабатываем данные из воронки продаж
        product_stats = {}
        total_views = 0
        total_carts = 0
        total_orders = 0
        total_order_sum = 0
        total_buyouts = 0
        total_buyout_sum = 0

        products_with_activity = 0  # Товары с хоть какой-то активностью
        products_with_sales = 0  # Товары с заказами/выкупами

        for item in all_data:
            product = item.get("product", {})
            statistic = item.get("statistic", {}).get("selected", {})

            nm_id = product.get("nmId")
            vendor_code = product.get("vendorCode", "")
            title = product.get("title", "")
            brand = product.get("brandName", "")
            category = product.get("subjectName", "")

            # Статистика за выбранный период (вчера)
            views = statistic.get("openCount", 0)
            carts = statistic.get("cartCount", 0)
            orders = statistic.get("orderCount", 0)
            order_sum = statistic.get("orderSum", 0)
            buyouts = statistic.get("buyoutCount", 0)
            buyout_sum = statistic.get("buyoutSum", 0)

            # Ищем артикул в БД (используем vendorCode или nmId)
            article = vendor_code if vendor_code else str(nm_id)

            # Проверяем активность
            has_activity = views > 0 or carts > 0 or orders > 0
            has_sales = orders > 0 or buyouts > 0

            if has_activity:
                products_with_activity += 1
            if has_sales:
                products_with_sales += 1

            # Сохраняем статистику по артикулу
            if article not in product_stats:
                product_stats[article] = {
                    'nm_id': nm_id,
                    'vendor_code': vendor_code,
                    'title': title[:100] if title else "",
                    'brand': brand,
                    'category': category,
                    'views': 0,
                    'carts': 0,
                    'orders': 0,
                    'order_sum': 0.0,
                    'buyouts': 0,
                    'buyout_sum': 0.0,
                    'conversion_to_cart': 0.0,
                    'conversion_to_order': 0.0
                }

            # Обновляем статистику
            product_stats[article]['views'] += views
            product_stats[article]['carts'] += carts
            product_stats[article]['orders'] += orders
            product_stats[article]['order_sum'] += order_sum
            product_stats[article]['buyouts'] += buyouts
            product_stats[article]['buyout_sum'] += buyout_sum

            # Рассчитываем конверсии
            if views > 0:
                product_stats[article]['conversion_to_cart'] = (carts / views) * 100
            if carts > 0:
                product_stats[article]['conversion_to_order'] = (orders / carts) * 100

            # Общая статистика
            total_views += views
            total_carts += carts
            total_orders += orders
            total_order_sum += order_sum
            total_buyouts += buyouts
            total_buyout_sum += buyout_sum

        logger.info(f"✅ Обработано артикулов: {len(product_stats)}")
        logger.info(f"📊 Товаров с активностью: {products_with_activity}")
        logger.info(f"💰 Товаров с продажами: {products_with_sales}")

        if products_with_sales == 0:
            await message.answer(
                f"📭 <b>Нет продаж за {yesterday_str}</b>\n\n"
                f"🏪 {account_name}\n"
                f"📅 {day_name}\n\n"
                f"<i>Статистика из API воронки продаж:</i>\n"
                f"• Всего товаров: {len(all_data)}\n"
                f"• Товаров с активностью: {products_with_activity}\n"
                f"• Просмотров: {total_views}\n"
                f"• В корзину: {total_carts}\n"
                f"• Заказов: {total_orders}\n"
                f"• Выкупов: {total_buyouts}\n\n"
                f"<i>Эндпоинт: /api/analytics/v3/sales-funnel/products</i>",
                reply_markup=get_main_keyboard()
            )
            return

        # Получаем кастомные названия для отчета
        custom_names = await product_manager.get_custom_names_dict(account.id)

        # Формируем отчет
        report_parts = []

        # Заголовок
        header = (
            f"<b>{account_name}</b>\n"
            f"📅 {yesterday_str} ({day_name})\n\n"
            f"<b>Сводный потоварный отчет:</b>\n"
            f"<i>Данные из API воронки продаж (/api/analytics/v3/sales-funnel/products)</i>\n"
        )
        report_parts.append(header)

        # Информация о методике расчета
        calculation_info = (
            f"\n<i>Методика расчета из воронки продаж:</i>\n"
            f"• <b>Просмотры (openCount)</b>: сколько раз открывали карточку товара\n"
            f"• <b>В корзину (cartCount)</b>: сколько раз добавляли в корзину\n"
            f"• <b>Заказы (orderCount)</b>: сколько раз заказывали\n"
            f"• <b>Сумма заказов (orderSum)</b>: общая сумма заказов\n"
            f"• <b>Выкупы (buyoutCount)</b>: сколько раз выкупали\n"
            f"• <b>Сумма выкупов (buyoutSum)</b>: общая сумма выкупов\n\n"
        )
        report_parts.append(calculation_info)

        # Обрабатываем каждый товар
        all_products_text = ""
        total_sales_qty = 0
        total_sales_amount = 0.0
        products_with_sales_count = 0

        # Сортируем товары по сумме выкупов (от большего к меньшему)
        sorted_products = sorted(
            product_stats.items(),
            key=lambda x: x[1]['buyout_sum'],
            reverse=True
        )

        for i, (article, stats) in enumerate(sorted_products, 1):
            # Пропускаем товары без выкупов
            if stats['buyout_sum'] == 0 and stats['order_sum'] == 0:
                continue

            products_with_sales_count += 1

            # Получаем название из БД или используем оригинальное
            display_name = custom_names.get(article, stats['title'] or article)

            # Форматируем суммы
            buyout_sum_formatted = f"{stats['buyout_sum']:,.2f}".replace(",", " ").replace(".", ",")
            order_sum_formatted = f"{stats['order_sum']:,.2f}".replace(",", " ").replace(".", ",")

            # Формируем строку для товара
            product_line = (
                f"\n<b>{i}. {display_name}</b>\n"
                f"   • Артикул: <code>{article}</code>\n"
                f"   • NMID: {stats['nm_id']}\n"
                f"   • Просмотры: {stats['views']:,}\n"
                f"   • В корзину: {stats['carts']:,}\n"
                f"   • Конверсия в корзину: {stats['conversion_to_cart']:.1f}%\n"
                f"   • Заказы: <b>{stats['orders']:,} шт.</b>\n"
                f"   • Сумма заказов: <b>{order_sum_formatted} ₽</b>\n"
                f"   • Выкупы: <b>{stats['buyouts']:,} шт.</b>\n"
                f"   • Сумма выкупов: <b>{buyout_sum_formatted} ₽</b>\n"
                f"   • Конверсия в заказ: {stats['conversion_to_order']:.1f}%\n"
            )

            # Добавляем категорию и бренд если есть
            if stats['category']:
                product_line += f"   • Категория: {stats['category']}\n"
            if stats['brand']:
                product_line += f"   • Бренд: {stats['brand']}\n"

            all_products_text += product_line
            total_sales_qty += stats['buyouts']
            total_sales_amount += stats['buyout_sum']

        # Формируем итоги
        total_amount_formatted = f"{total_sales_amount:,.2f}".replace(",", " ").replace(".", ",")
        total_views_formatted = f"{total_views:,}"
        total_carts_formatted = f"{total_carts:,}"
        total_orders_formatted = f"{total_orders:,}"
        total_buyouts_formatted = f"{total_buyouts:,}"

        # Общая конверсия
        overall_cart_conversion = (total_carts / total_views * 100) if total_views > 0 else 0
        overall_order_conversion = (total_orders / total_carts * 100) if total_carts > 0 else 0

        report_parts.append(all_products_text)

        # Итоги
        footer = (
            f"\n{'─' * 40}\n"
            f"📊 <b>ИТОГО ПО МАГАЗИНУ:</b>\n"
            f"📦 Всего товаров: {len(all_data)}\n"
            f"📈 Товаров с активностью: {products_with_activity}\n"
            f"💰 Товаров с продажами: {products_with_sales_count}\n"
            f"👁️ Общее просмотров: {total_views_formatted}\n"
            f"🛒 В корзину: {total_carts_formatted}\n"
            f"📥 Заказов: {total_orders_formatted}\n"
            f"✅ Выкупов: <b>{total_buyouts_formatted} шт.</b>\n"
            f"💰 Сумма выкупов: <b>{total_amount_formatted} ₽</b>\n"
            f"📊 Конверсия в корзину: {overall_cart_conversion:.1f}%\n"
            f"📊 Конверсия в заказ: {overall_order_conversion:.1f}%\n"
        )
        report_parts.append(footer)

        # Детальная статистика API
        detail_stats = (
            f"\n<i>Детальная статистика API воронки продаж:</i>\n"
            f"• Использован эндпоинт: /api/analytics/v3/sales-funnel/products\n"
            f"• Период сравнения: неделя назад (7 дней)\n"
            f"• Лимит пагинации: 500 товаров за запрос\n"
            f"• Обработано записей: {len(all_data)}\n"
            f"• Уникальных артикулов: {len(product_stats)}\n\n"
            f"<i>Использованные поля API:</i>\n"
            f"• product.nmId - внутренний ID товара WB\n"
            f"• product.vendorCode - ваш артикул\n"
            f"• product.title - название товара\n"
            f"• product.brandName - бренд\n"
            f"• product.subjectName - категория\n"
            f"• statistic.selected.openCount - просмотры\n"
            f"• statistic.selected.cartCount - в корзину\n"
            f"• statistic.selected.orderCount - заказы\n"
            f"• statistic.selected.orderSum - сумма заказов\n"
            f"• statistic.selected.buyoutCount - выкупы\n"
            f"• statistic.selected.buyoutSum - сумма выкупов\n"
        )
        report_parts.append(detail_stats)

        # Отправляем отчет
        full_report = "".join(report_parts)

        # Разбиваем на части если слишком длинный
        if len(full_report) > 4000:
            # Отправляем первую часть
            first_part = header + calculation_info + all_products_text[:2000]
            await message.answer(first_part, parse_mode='HTML', reply_markup=get_main_keyboard())

            # Отправляем оставшуюся часть
            remaining_part = all_products_text[2000:] + footer + detail_stats
            await message.answer(remaining_part, parse_mode='HTML', reply_markup=get_main_keyboard())
        else:
            await message.answer(full_report, parse_mode='HTML', reply_markup=get_main_keyboard())

    except ImportError as e:
        logger.error(f"❌ Ошибка импорта: {e}")
        await message.answer(
            f"❌ <b>Ошибка импорта модулей</b>\n\n"
            f"<code>{str(e)}</code>\n\n"
            f"<i>Убедитесь что файл sales_funnel_yesterday.py находится в той же директории</i>",
            parse_mode='HTML',
            reply_markup=get_main_keyboard()
        )
    except Exception as e:
        logger.error(f"❌ Ошибка при сборе статистики по товарам за вчера: {e}", exc_info=True)

        error_msg = (
            f"❌ <b>Ошибка при сборе статистики</b>\n\n"
            f"<code>{str(e)[:200]}</code>\n\n"
            f"<i>Проверьте логи для подробностей</i>\n"
            f"<i>Использован эндпоинт: /api/analytics/v3/sales-funnel/products</i>"
        )

        await message.answer(error_msg, parse_mode='HTML', reply_markup=get_main_keyboard())
