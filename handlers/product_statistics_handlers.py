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

        header_text = f"<b>📊 СТАТИСТИКА ЗА ВЧЕРА</b>\n{date_str} ({day_name})\nВсего магазинов: {len(all_accounts)}\n"
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
                    # Сортируем товары по количеству заказов
                    sorted_products = sorted(
                        stats["products"],
                        key=lambda x: x['orders'],
                        reverse=True
                    )

                    # Только товары с продажами
                    products_with_sales = [p for p in sorted_products if p['orders'] > 0]

                    if products_with_sales:
                        # Начало сообщения для магазина
                        response_text = f"<b>🏪 {account_name}</b>\n\n"

                        # Добавляем товары с продажами
                        for i, product in enumerate(products_with_sales, 1):
                            # Берем кастомное название из БД, если есть, иначе название из API
                            display_name = custom_names.get(product['article'])
                            if not display_name:
                                display_name = product['title']

                            # Форматируем числа
                            views_formatted = f"{product['views']:,}"
                            carts_formatted = f"{product['carts']:,}"
                            orders_formatted = f"{product['orders']:,}"
                            order_sum_formatted = f"{product['order_sum']:,.2f} ₽".replace(",", " ").replace(".", ",")

                            # Добавляем товар в формате из образца
                            response_text += f"<b>{i}. {display_name}</b>\n"
                            response_text += f"   • Артикул: {product['article']}\n"
                            response_text += f"   • Просмотры: {views_formatted}\n"
                            response_text += f"   • В корзине: {carts_formatted}\n"
                            response_text += f"   • Конверсия в корзину: {product['conversion_to_cart']:.1f}%\n"
                            response_text += f"   • Конверсия в заказ: {product['conversion_to_order']:.1f}%\n"
                            response_text += f"   • <b>Заказы: {orders_formatted} шт.</b>\n"
                            response_text += f"   • <b>Сумма заказов: {order_sum_formatted}</b>\n\n"

                        # Итоги по магазину
                        total_order_sum_formatted = f"{stats['total_order_sum']:,.2f} ₽".replace(",", " ").replace(".", ",")

                        response_text += "<b>ИТОГО ПО МАГАЗИНУ</b>\n"
                        response_text += f"<b>Заказов: {stats['total_orders']:,}</b>\n"
                        response_text += f"<b>Заказано на сумму: {total_order_sum_formatted}</b>\n"
                        response_text += f"Всего товаров: {stats['total_products']:,}\n"
                        response_text += f"Товаров с продажами: {stats['products_with_sales']:,}\n"
                        response_text += f"Общее просмотров: {stats['total_views']:,}\n"
                        response_text += f"Конверсия в корзину: {stats['overall_cart_conversion']:.1f}%\n"
                        response_text += f"Конверсия в заказ: {stats['overall_order_conversion']:.1f}%\n"

                        # Отправляем сообщение
                        await callback.message.answer(response_text)

                        successful_accounts += 1

                    else:
                        # Магазин без продаж
                        await callback.message.answer(
                            f"<b>🏪 {account_name}</b>\n\n"
                            f"Нет продаж за этот день\n\n"
                            f"Статистика из API:\n"
                            f"Всего товаров: {stats['total_products']:,}\n"
                            f"Просмотров: {stats['total_views']:,}\n"
                            f"В корзину: {stats['total_carts']:,}\n"
                            f"Заказов: {stats['total_orders']:,}"
                        )
                else:
                    # Магазин без продаж
                    await callback.message.answer(
                        f"<b>🏪 {account_name}</b>\n\n"
                        f"Нет продаж за этот день\n\n"
                        f"Статистика из API:\n"
                        f"Всего товаров: {stats['total_products']:,}\n"
                        f"Просмотров: {stats['total_views']:,}\n"
                        f"В корзину: {stats['total_carts']:,}\n"
                        f"Заказов: {stats['total_orders']:,}"
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
                    f"Ошибка: {display_error}\n"
                    f"Детали: {error_message[:100]}"
                )

                # Задержка перед следующим магазином в случае ошибки
                await asyncio.sleep(5)

            # Задержка между запросами к разным магазинам
            if account_index < len(all_accounts):
                await asyncio.sleep(10)

        # Финальное сообщение
        await callback.message.answer(
            f"Обработка завершена\n"
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
            "Произошла непредвиденная ошибка\n"
            f"Детали: {str(e)[:100]}\n"
            "Попробуйте позже.",
            reply_markup=get_stats_keyboard()
        )
