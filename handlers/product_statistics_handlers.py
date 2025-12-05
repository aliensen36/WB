# handlers/product_statistics_handlers.py
import asyncio
import logging
from datetime import datetime, timedelta
from aiogram import Router, F
from aiogram.types import CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession
from database.account_manager import AccountManager
from database.product_manager import ProductManager
from functions.yesterday_product_statistics import YesterdayProductStatistics
from keyboards.statistics_kb import get_stats_keyboard

logger = logging.getLogger(__name__)

product_statistics_router = Router()


@product_statistics_router.callback_query(F.data == "yesterday_stats")
async def handle_yesterday_stats(callback: CallbackQuery, session: AsyncSession):
    """Показать детальную статистику по товарам за вчера для всех магазинов"""

    await callback.answer()

    logger.info("Получение статистики за вчера")

    try:
        loading_msg = await callback.message.answer(
            "Получение статистики по товарам за вчера..."
        )

        account_manager = AccountManager(session)
        all_accounts = await account_manager.get_all_accounts()

        if not all_accounts:
            await loading_msg.delete()
            await callback.message.answer(
                "Нет добавленных магазинов",
                reply_markup=get_stats_keyboard()
            )
            return

        logger.info(f"Найдено магазинов для обработки: {len(all_accounts)}")

        successful_accounts = 0

        # Получаем дату вчерашнего дня
        yesterday_date_obj = datetime.now() - timedelta(days=1)
        date_str = yesterday_date_obj.strftime("%d.%m.%Y")
        days = ["Понедельник", "Вторник", "Среда", "Четверг", "Пятница", "Суббота", "Воскресенье"]
        day_name = days[yesterday_date_obj.weekday()]

        # Заголовок статистики
        await loading_msg.delete()

        header_text = (f"<b>📊 СТАТИСТИКА ЗА ВЧЕРА</b>\n{date_str} ({day_name})\n"
                       f"Всего магазинов: {len(all_accounts)}\n\n"
                       f"<i>(Только товары с заказами)</i>")
        await callback.message.answer(header_text)

        # Обрабатываем КАЖДЫЙ магазин отдельно
        for account_index, account in enumerate(all_accounts, 1):
            account_name = account.account_name or f"Магазин {account.id}"
            logger.info(f"[{account_index}/{len(all_accounts)}] Обрабатываю магазин: {account_name}")

            try:
                # Получаем статистику по товарам для текущего магазина
                yesterday_stats = YesterdayProductStatistics(account.api_key)
                stats = await yesterday_stats.get_yesterday_product_stats()

                logger.info(f"[{account_name}] Получено товаров: {len(stats.get('all_products', []))}")
                logger.info(
                    f"[{account_name}] Выкупов: {stats.get('total_buyouts', 0)} шт. на {stats.get('total_buyout_sum', 0):.2f} руб.")

                # Сохраняем товары в БД
                product_manager = ProductManager(session)
                saved_products_count = 0
                all_products_for_save = stats.get("all_products", [])

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

                # Получаем кастомные названия из БД
                custom_names = await product_manager.get_custom_names_dict(account.id)

                # Формируем сообщение для магазина
                if stats["total_buyouts"] > 0 or stats["total_orders"] > 0:
                    # Сортируем товары по количеству выкупов (приоритет), затем по заказам
                    sorted_products = sorted(
                        stats["products"],
                        key=lambda x: (x['buyouts'], x['orders']),
                        reverse=True
                    )

                    # Только товары с продажами или выкупами
                    products_with_activity = [p for p in sorted_products if p['orders'] > 0 or p['buyouts'] > 0]

                    if products_with_activity:
                        # Разбиваем на части и отправляем
                        await send_store_statistics_parts(
                            callback,
                            account_name,
                            products_with_activity,
                            custom_names,
                            stats
                        )

                        successful_accounts += 1

                    else:
                        # Магазин без продаж
                        await callback.message.answer(
                            f"<b>🏪 {account_name}</b>\n\n"
                            f"Нет продаж за этот день\n\n"
                            f"<i>Статистика из API:</i>\n"
                            f"Всего товаров: {stats['total_products']:,}\n"
                            f"Просмотров: {stats['total_views']:,}\n"
                            f"В корзину: {stats['total_carts']:,}\n"
                            f"Заказов: {stats['total_orders']:,}\n"
                            f"Выкупов: {stats['total_buyouts']:,}"
                        )
                else:
                    # Магазин без продаж
                    await callback.message.answer(
                        f"<b>🏪 {account_name}</b>\n\n"
                        f"Нет продаж за этот день\n\n"
                        f"<i>Статистика из API:</i>\n"
                        f"Всего товаров: {stats['total_products']:,}\n"
                        f"Просмотров: {stats['total_views']:,}\n"
                        f"В корзину: {stats['total_carts']:,}\n"
                        f"Заказов: {stats['total_orders']:,}\n"
                        f"Выкупов: {stats['total_buyouts']:,}"
                    )

            except Exception as e:
                error_message = str(e)
                logger.error(f"[{account_name}] Ошибка при получении статистики: {error_message}")

                if "Неверный API ключ" in error_message:
                    display_error = "Неверный API ключ"
                elif "Превышен лимит запросов" in error_message:
                    display_error = "Превышен лимит запросов API"
                elif "Таймаут запроса" in error_message:
                    display_error = "Таймаут запроса"
                else:
                    display_error = "Ошибка подключения к API"

                await callback.message.answer(
                    f"<b>🏪 {account_name}</b>\n"
                    f"<b>Ошибка:</b> {display_error}\n"
                    f"<i>Детали: {error_message[:100]}</i>"
                )

                # Задержка перед следующим магазином в случае ошибки
                await asyncio.sleep(5)

            # Задержка между запросами к разным магазинам
            if account_index < len(all_accounts):
                await asyncio.sleep(10)

        # Финальное сообщение
        await callback.message.answer(
            f"<b>Обработка завершена</b>\n"
            f"Успешно обработано: {successful_accounts} из {len(all_accounts)} магазинов",
            reply_markup=get_stats_keyboard()
        )

        logger.info(f"Статистика успешно отправлена для {successful_accounts}/{len(all_accounts)} магазинов")

    except Exception as e:
        logger.error(f"Неожиданная ошибка при получении статистики за вчера: {e}")
        try:
            await loading_msg.delete()
        except:
            pass

        await callback.message.answer(
            "<b>Произошла непредвиденная ошибка</b>\n"
            f"<i>Детали: {str(e)[:100]}</i>\n"
            "Попробуйте позже.",
            reply_markup=get_stats_keyboard()
        )


async def send_store_statistics_parts(callback: CallbackQuery, account_name: str,
                                      products_with_activity: list, custom_names: dict, stats: dict):
    """Разбивает статистику магазина на части и отправляет отдельными сообщениями"""

    # Максимальное количество товаров в одном сообщении (с HTML тегами нужно меньше)
    MAX_PRODUCTS_PER_MESSAGE = 8

    # Форматируем итоговые суммы
    total_order_sum_formatted = f"{stats['total_order_sum']:,.2f} ₽".replace(",", " ").replace(".", ",")
    total_buyout_sum_formatted = f"{stats['total_buyout_sum']:,.2f} ₽".replace(",", " ").replace(".", ",")

    # Рассчитываем процент выкупа
    if stats['total_orders'] > 0:
        buyout_percent = (stats['total_buyouts'] / stats['total_orders']) * 100
    else:
        buyout_percent = 0

    # Отправляем заголовок магазина
    await callback.message.answer(f"<b>🏪 {account_name}</b>")

    # Разбиваем товары на части
    total_products = len(products_with_activity)

    for part_num, chunk_start in enumerate(range(0, total_products, MAX_PRODUCTS_PER_MESSAGE)):
        chunk_end = min(chunk_start + MAX_PRODUCTS_PER_MESSAGE, total_products)
        chunk = products_with_activity[chunk_start:chunk_end]

        # Формируем часть сообщения
        part_text = ""

        # Если это первая часть и товаров много, добавляем информацию
        if part_num == 0 and total_products > MAX_PRODUCTS_PER_MESSAGE:
            part_text += f"<i>(товары 1-{MAX_PRODUCTS_PER_MESSAGE} из {total_products})</i>\n\n"

        # Добавляем товары из текущего чанка
        for i, product in enumerate(chunk, chunk_start + 1):
            # Берем кастомное название из БД, если есть, иначе название из API
            display_name = custom_names.get(product['article'])
            if not display_name:
                display_name = product['title']

            # Форматируем числа
            views_formatted = f"{product['views']:,}"
            carts_formatted = f"{product['carts']:,}"
            orders_formatted = f"{product['orders']:,}"
            order_sum_formatted = f"{product['order_sum']:,.2f} ₽".replace(",", " ").replace(".", ",")
            buyouts_formatted = f"{product['buyouts']:,}"
            buyout_sum_formatted = f"{product['buyout_sum']:,.2f} ₽".replace(",", " ").replace(".", ",")

            # Рассчитываем процент выкупа для товара
            if product['orders'] > 0:
                product_buyout_percent = (product['buyouts'] / product['orders']) * 100
                buyout_percent_formatted = f"{product_buyout_percent:.1f}%"
            else:
                buyout_percent_formatted = "0%"

            # Добавляем товар с выкупами
            part_text += f"<b>{i}. {display_name}</b>\n"
            part_text += f"   • Артикул: {product['article']}\n"
            part_text += f"   • Просмотры: {views_formatted}\n"
            part_text += f"   • В корзине: {carts_formatted}\n"
            part_text += f"   • Конверсия в корзину: {product['conversion_to_cart']:.1f}%\n"
            part_text += f"   • Конверсия в заказ: {product['conversion_to_order']:.1f}%\n"
            part_text += f"   • <b>Заказы: {orders_formatted} шт. на {order_sum_formatted}</b>\n"
            part_text += f"   • <b>Выкупы: {buyouts_formatted} шт. на {buyout_sum_formatted}</b>\n\n"


        # Если это не последняя часть, добавляем информацию о продолжении
        if chunk_end < total_products:
            next_chunk_start = chunk_end
            next_chunk_end = min(next_chunk_start + MAX_PRODUCTS_PER_MESSAGE, total_products)
            part_text += f"<i>... продолжение ({next_chunk_start + 1}-{next_chunk_end}) ...</i>\n"

        # Отправляем часть сообщения
        await callback.message.answer(part_text)

        # Небольшая задержка между сообщениями
        await asyncio.sleep(0.3)

    # Создаем итоговую часть с ВЫКУПАМИ
    final_part = "<b>📊 ИТОГО ПО МАГАЗИНУ</b>\n"
    final_part += "═" * 30 + "\n"

    # Блок с заказами
    final_part += f"<b>📈 ЗАКАЗЫ:</b>\n"
    final_part += f"   • Заказов: <b>{stats['total_orders']:,} шт.</b>\n"
    final_part += f"   • Сумма заказов: <b>{total_order_sum_formatted}</b>\n\n"

    # Блок с выкупами (ДОБАВЛЕНО)
    final_part += f"<b>✅ ВЫКУПЫ:</b>\n"
    final_part += f"   • Выкупов: <b>{stats['total_buyouts']:,} шт.</b>\n"
    final_part += f"   • Сумма выкупов: <b>{total_buyout_sum_formatted}</b>\n\n"

    # Общая статистика
    final_part += f"<b>📋 ОБЩАЯ СТАТИСТИКА:</b>\n"
    final_part += f"   • Всего товаров: {stats['total_products']:,}\n"
    final_part += f"   • Общее просмотров: {stats['total_views']:,}\n"
    final_part += f"   • Конверсия в корзину: {stats['overall_cart_conversion']:.1f}%\n"
    final_part += f"   • Конверсия в заказ: {stats['overall_order_conversion']:.1f}%\n"

    # Отправляем итоговую часть
    await callback.message.answer(final_part)
