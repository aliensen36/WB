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

    logger.info("🔍 ВЫЗВАН ОБРАБОТЧИК yesterday_stats - начинаю обработку ВСЕХ магазинов")

    try:
        loading_msg = await callback.message.answer(
            "📊 <b>Получение статистики по товарам за вчера...</b>\n\n"
            "🔄 Загружаем данные для всех магазинов...\n"
            "<i>Это может занять несколько минут</i>",
            parse_mode="HTML"
        )

        account_manager = AccountManager(session)
        all_accounts = await account_manager.get_all_accounts()

        if not all_accounts:
            await loading_msg.delete()
            await callback.message.answer(
                "❌ <b>Нет добавленных магазинов</b>",
                reply_markup=get_stats_keyboard()
            )
            return

        logger.info(f"🏪 Найдено магазинов для обработки: {len(all_accounts)}")

        all_responses = []
        successful_accounts = 0
        total_saved_products = 0

        # Обрабатываем КАЖДЫЙ магазин
        for account_index, account in enumerate(all_accounts, 1):
            account_name = account.account_name or f"Магазин {account.id}"
            logger.info(
                f"🏪 [{account_index}/{len(all_accounts)}] Обрабатываю магазин: {account_name} (ID: {account.id})")

            try:
                # Получаем полную статистику по товарам для текущего магазина
                yesterday_stats = YesterdayProductStatistics(account.api_key)
                stats = await yesterday_stats.get_yesterday_product_stats()

                logger.info(
                    f"📊 [{account_name}] Получено статистики: {len(stats.get('products', []))} товаров для отображения")

                # Если нет данных
                if stats["total_buyouts"] == 0 and stats["total_orders"] == 0:
                    logger.info(f"📭 [{account_name}] Нет продаж за {stats['date']}")
                    response_text = f"<b>{account_name}</b>\n"
                    response_text += f"📅 {stats['date']}\n\n"
                    response_text += "📭 <b>Нет продаж за этот день</b>\n\n"
                    response_text += f"<i>Статистика из API:</i>\n"
                    response_text += f"• Всего товаров: {stats['total_products']:,}\n"
                    response_text += f"• Товаров с активностью: {stats['active_products']:,}\n"
                    response_text += f"• Просмотров: {stats['total_views']:,}\n"
                    response_text += f"• В корзину: {stats['total_carts']:,}\n"
                    response_text += f"• Заказов: {stats['total_orders']:,}\n"
                    response_text += f"• Выкупов: {stats['total_buyouts']:,}\n"

                    all_responses.append(response_text)
                    continue

                # ИНИЦИАЛИЗИРУЕМ ProductManager для текущего магазина
                product_manager = ProductManager(session)

                # СОХРАНЯЕМ ТОВАРЫ В БД ПРИ ЗАГРУЗКЕ СТАТИСТИКИ
                logger.info(f"🔄 [{account_name}] Начинаю сохранение товаров в БД...")
                saved_products_count = 0
                updated_names_count = 0

                # Используем все товары для сохранения
                all_products_for_save = stats.get("all_products", [])

                for product_data in all_products_for_save:
                    try:
                        article = product_data.get('article')
                        if article:
                            # Сохраняем товар в БД (создаем или получаем существующий)
                            product = await product_manager.get_or_create_product(
                                seller_account_id=account.id,
                                supplier_article=article
                            )
                            saved_products_count += 1

                            # Сохраняем название товара из API, если его еще нет в БД
                            title = product_data.get('title')
                            if title and not product.custom_name:
                                # Обрезаем слишком длинные названия
                                short_title = title[:100] if len(title) > 100 else title
                                success = await product_manager.update_custom_name(
                                    seller_account_id=account.id,
                                    supplier_article=article,
                                    custom_name=short_title
                                )
                                if success:
                                    updated_names_count += 1
                                    logger.debug(f"📝 [{account_name}] Обновлено название для {article}: {short_title}")

                    except Exception as e:
                        logger.error(
                            f"❌ [{account_name}] Ошибка при сохранении товара {product_data.get('article', 'UNKNOWN')}: {e}")

                logger.info(
                    f"✅ [{account_name}] Сохранено товаров в БД: {saved_products_count} из {len(all_products_for_save)}")
                total_saved_products += saved_products_count

                # Получаем кастомные названия из БД
                custom_names = await product_manager.get_custom_names_dict(account.id)
                logger.info(f"📚 [{account_name}] Загружено кастомных названий из БД: {len(custom_names)}")

                # Сортируем товары по количеству заказов (по убыванию)
                sorted_products = sorted(
                    stats["products"],
                    key=lambda x: x['orders'],
                    reverse=True
                )

                # Ограничиваем количество товаров для вывода
                products_to_show = sorted_products[:10]  # Показываем топ-10 товаров для каждого магазина

                # Формируем заголовок
                days = ["Понедельник", "Вторник", "Среда", "Четверг", "Пятница", "Суббота", "Воскресенье"]
                yesterday_date_obj = datetime.now() - timedelta(days=1)
                day_name = days[yesterday_date_obj.weekday()]

                response_text = f"<b>🏪 {account_name}</b>\n"
                response_text += f"📅 {stats['date']} ({day_name})\n\n"
                response_text += f"📦 <i>В БД сохранено: {saved_products_count} товаров</i>\n\n"

                # Добавляем товары только если они есть
                if products_to_show:
                    for i, product in enumerate(products_to_show, 1):
                        # Получаем название из БД или используем оригинальное
                        display_name = custom_names.get(product['article'], product['title'])

                        # Форматируем числа с разделителями тысяч
                        views_formatted = f"{product['views']:,}"
                        carts_formatted = f"{product['carts']:,}"
                        orders_formatted = f"{product['orders']:,}"

                        # Форматируем сумму заказов
                        order_sum_formatted = f"{product['order_sum']:,.2f} ₽".replace(",", " ").replace(".", ",")

                        # Добавляем товар в формате как в примере
                        response_text += f"<b>{i}. {display_name}</b>\n"
                        response_text += f"   • Артикул: {product['article']}\n"
                        response_text += f"   • Просмотры: {views_formatted}\n"
                        response_text += f"   • В корзину: {carts_formatted}\n"
                        response_text += f"   • Конверсия в корзину: {product['conversion_to_cart']:.1f}%\n"
                        response_text += f"   • Конверсия в заказ: {product['conversion_to_order']:.1f}%\n"
                        response_text += f"   • Заказы: <b>{orders_formatted}</b> шт.\n"
                        response_text += f"   • Сумма заказов: <b>{order_sum_formatted}</b>\n\n"

                # Форматируем итоговые суммы
                total_order_sum_formatted = f"{stats['total_order_sum']:,.2f} ₽".replace(",", " ").replace(".", ",")

                # Добавляем итоги
                response_text += "📊 <b>ИТОГО ПО МАГАЗИНУ:</b>\n"
                response_text += f"📥 Заказов: {stats['total_orders']:,}\n"
                response_text += f"   Заказано на сумму: {total_order_sum_formatted}\n"
                response_text += f"📦 Всего товаров: {stats['total_products']:,}\n"
                response_text += f"💰 Товаров с продажами: {stats['products_with_sales']:,}\n"
                response_text += f"👁 Общее просмотров: {stats['total_views']:,}\n"
                response_text += f"📊 Конверсия в корзину: {stats['overall_cart_conversion']:.1f}%\n"
                response_text += f"📊 Конверсия в заказ: {stats['overall_order_conversion']:.1f}%\n\n"
                response_text += "─" * 30 + "\n\n"

                all_responses.append(response_text)
                successful_accounts += 1

            except Exception as e:
                error_message = str(e)
                logger.error(f"❌ [{account_name}] Ошибка при получении статистики: {error_message}")

                # Обработка конкретных ошибок API
                if "Неверный API ключ" in error_message:
                    display_error = "❌ Неверный API ключ"
                elif "Превышен лимит запросов" in error_message:
                    display_error = "⚠️ Превышен лимит запросов API"
                elif "Таймаут запроса" in error_message:
                    display_error = "⏱️ Таймаут запроса"
                else:
                    display_error = "❌ Ошибка подключения к API"

                error_text = f"<b>🏪 {account_name}</b>\n"
                error_text += f"❌ <b>Ошибка:</b> {display_error}\n"
                error_text += f"<i>Детали: {error_message[:100]}</i>\n\n"
                error_text += "─" * 30 + "\n\n"

                all_responses.append(error_text)

                # Задержка перед следующим магазином в случае ошибки
                await asyncio.sleep(5)

            # Задержка между запросами к разным магазинам
            if account_index < len(all_accounts):
                await asyncio.sleep(10)

        # Удаляем сообщение о загрузке
        await loading_msg.delete()

        # Формируем общий заголовок
        total_summary = f"📊 <b>СТАТИСТИКА ЗА ВЧЕРА</b>\n\n"
        total_summary += f"📅 {stats['date']}\n"
        total_summary += f"🏪 Всего магазинов: {len(all_accounts)}\n"
        total_summary += f"✅ Успешно обработано: {successful_accounts}\n"
        total_summary += f"📦 Сохранено товаров: {total_saved_products}\n\n"
        total_summary += "─" * 30 + "\n\n"

        # Собираем все ответы в одно сообщение
        final_response = total_summary + "".join(all_responses)

        # Проверяем длину сообщения
        if len(final_response) > 4000:
            # Разбиваем на части
            parts = []
            current_part = ""
            current_length = 0

            # Разделяем по магазинам
            lines = final_response.split('\n')
            current_part_lines = []

            for line in lines:
                # Если строка начинается с "🏪 " - это новый магазин
                if line.startswith("🏪 ") and current_length > 2000:
                    # Сохраняем текущую часть
                    parts.append('\n'.join(current_part_lines))
                    # Начинаем новую часть
                    current_part_lines = [line]
                    current_length = len(line) + 1
                else:
                    current_part_lines.append(line)
                    current_length += len(line) + 1

            # Добавляем последнюю часть
            if current_part_lines:
                parts.append('\n'.join(current_part_lines))

            # Отправляем первую часть с клавиатурой
            await callback.message.answer(
                parts[0],
                reply_markup=get_stats_keyboard(),
                parse_mode="HTML"
            )

            # Отправляем остальные части
            for part in parts[1:]:
                await callback.message.answer(
                    part,
                    parse_mode="HTML"
                )
        else:
            # Отправляем одним сообщением
            await callback.message.answer(
                final_response,
                reply_markup=get_stats_keyboard(),
                parse_mode="HTML"
            )

        logger.info(f"✅ Статистика успешно отправлена для {successful_accounts}/{len(all_accounts)} магазинов")

    except Exception as e:
        logger.error(f"Неожиданная ошибка при получении статистики за вчера: {e}")
        try:
            await loading_msg.delete()
        except:
            pass

        await callback.message.answer(
            "❌ <b>Произошла непредвиденная ошибка</b>\n\n"
            f"<i>{str(e)[:100]}</i>\n\n"
            "Попробуйте позже.",
            reply_markup=get_stats_keyboard(),
            parse_mode="HTML"
        )
