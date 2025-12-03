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
    """Показать детальную статистику по товарам за вчера"""

    await callback.answer()

    logger.info("🔍 ВЫЗВАН ОБРАБОТЧИК yesterday_stats - начинаю обработку")

    try:
        loading_msg = await callback.message.answer(
            "📊 <b>Получение статистики по товарам за вчера...</b>\n\n"
            "🔄 Загружаем данные...\n"
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

        account = all_accounts[0]
        account_name = account.account_name or f"Магазин {account.id}"

        logger.info(f"🏪 Обрабатываю магазин: {account_name} (ID: {account.id})")

        try:
            # Получаем полную статистику по товарам
            yesterday_stats = YesterdayProductStatistics(account.api_key)
            stats = await yesterday_stats.get_yesterday_product_stats()

            logger.info(f"📊 Получено статистики: {len(stats.get('products', []))} товаров для отображения")
            logger.info(f"📦 Всего товаров для сохранения: {len(stats.get('all_products', []))}")

            # Если нет данных
            if stats["total_buyouts"] == 0 and stats["total_orders"] == 0:
                await loading_msg.delete()
                await callback.message.answer(
                    f"📭 <b>Нет продаж за {stats['date']}</b>\n\n"
                    f"🏪 {account_name}\n"
                    f"📅 {stats['date']}\n\n"
                    f"<i>Статистика из API воронки продаж:</i>\n"
                    f"• Всего товаров: {stats['total_products']:,}\n"
                    f"• Товаров с активностью: {stats['active_products']:,}\n"
                    f"• Просмотров: {stats['total_views']:,}\n"
                    f"• В корзину: {stats['total_carts']:,}\n"
                    f"• Заказов: {stats['total_orders']:,}\n"
                    f"• Выкупов: {stats['total_buyouts']:,}\n\n"
                    f"<i>Эндпоинт: /api/analytics/v3/sales-funnel/products</i>",
                    reply_markup=get_stats_keyboard(),
                    parse_mode="HTML"
                )
                return

            # ИНИЦИАЛИЗИРУЕМ ProductManager
            product_manager = ProductManager(session)

            # СОХРАНЯЕМ ТОВАРЫ В БД ПРИ ЗАГРУЗКЕ СТАТИСТИКИ
            logger.info(f"🔄 Начинаю сохранение товаров в БД...")
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
                                logger.debug(f"📝 Обновлено название для {article}: {short_title}")

                except Exception as e:
                    logger.error(f"❌ Ошибка при сохранении товара {product_data.get('article', 'UNKNOWN')}: {e}")

            logger.info(f"✅ Сохранено товаров в БД: {saved_products_count} из {len(all_products_for_save)}")
            logger.info(f"📝 Обновлено названий: {updated_names_count}")

            # Получаем кастомные названия из БД (теперь там уже есть товары)
            custom_names = await product_manager.get_custom_names_dict(account.id)
            logger.info(f"📚 Загружено кастомных названий из БД: {len(custom_names)}")

            # Сортируем товары по количеству заказов (по убыванию)
            sorted_products = sorted(
                stats["products"],
                key=lambda x: x['orders'],
                reverse=True
            )

            # Ограничиваем количество товаров для вывода
            products_to_show = sorted_products[:20]

            # Формируем заголовок
            days = ["Понедельник", "Вторник", "Среда", "Четверг", "Пятница", "Суббота", "Воскресенье"]
            yesterday_date_obj = datetime.now() - timedelta(days=1)
            day_name = days[yesterday_date_obj.weekday()]

            response_text = f"<b>{account_name}</b>\n"
            response_text += f"📅 {stats['date']} ({day_name})\n\n"

            # Добавляем информацию о сохраненных товарах
            response_text += f"📦 <i>В БД сохранено: {saved_products_count} товаров</i>\n\n"

            # Добавляем товары
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

            # Добавляем итоги (ТОЧНО как в примере)
            response_text += "📊 <b>ИТОГО ПО МАГАЗИНУ:</b>\n"
            response_text += f"📥 Заказов: {stats['total_orders']:,}\n"
            response_text += f"   Заказано на сумму: {total_order_sum_formatted}\n"
            response_text += f"📦 Всего товаров: {stats['total_products']:,}\n"
            response_text += f"💰 Товаров с продажами: {stats['products_with_sales']:,}\n"
            response_text += f"👁 Общее просмотров: {stats['total_views']:,}\n"
            response_text += f"📊 Конверсия в корзину: {stats['overall_cart_conversion']:.1f}%\n"
            response_text += f"📊 Конверсия в заказ: {stats['overall_order_conversion']:.1f}%\n"

            # Удаляем сообщение о загрузке
            await loading_msg.delete()

            # Проверяем длину сообщения
            if len(response_text) > 4000:
                # Разбиваем на части
                lines = response_text.split('\n')
                part1_lines = []
                part2_lines = []
                current_length = 0

                for line in lines:
                    if current_length < 2000:
                        part1_lines.append(line)
                        current_length += len(line) + 1
                    else:
                        part2_lines.append(line)

                part1 = '\n'.join(part1_lines) + "\n\n<i>... продолжение ниже ...</i>"
                part2 = '\n'.join(part2_lines)

                await callback.message.answer(
                    part1,
                    reply_markup=get_stats_keyboard(),
                    parse_mode="HTML"
                )
                await callback.message.answer(
                    part2,
                    parse_mode="HTML"
                )
            else:
                await callback.message.answer(
                    response_text,
                    reply_markup=get_stats_keyboard(),
                    parse_mode="HTML"
                )

        except Exception as e:
            error_message = str(e)

            # Обработка конкретных ошибок API
            if "Неверный API ключ" in error_message:
                display_error = "❌ Неверный API ключ"
            elif "Превышен лимит запросов" in error_message:
                display_error = "⚠️ Превышен лимит запросов API"
            elif "Таймаут запроса" in error_message:
                display_error = "⏱️ Таймаут запроса"
            else:
                display_error = "❌ Ошибка подключения к API"

            await loading_msg.delete()
            await callback.message.answer(
                f"❌ <b>Ошибка при получении статистики</b>\n\n"
                f"<b>{account_name}</b>\n"
                f"{display_error}\n\n"
                f"<i>Детали: {error_message[:100]}</i>\n\n"
                f"Попробуйте позже.",
                reply_markup=get_stats_keyboard(),
                parse_mode="HTML"
            )

            logger.error(f"Ошибка для {account_name}: {error_message}")

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


@product_statistics_router.callback_query(F.data == "test_products_save")
async def test_products_save(callback: CallbackQuery, session: AsyncSession):
    """Тестовая команда для проверки сохранения товаров"""
    await callback.answer()

    try:
        product_manager = ProductManager(session)
        account_manager = AccountManager(session)

        accounts = await account_manager.get_all_accounts()
        if not accounts:
            await callback.message.answer("❌ Нет аккаунтов")
            return

        account = accounts[0]

        # 1. Создаем тестовый товар
        test_product = await product_manager.get_or_create_product(
            seller_account_id=account.id,
            supplier_article=f"TEST_{callback.from_user.id}"
        )

        # 2. Проверяем количество товаров
        all_products = await product_manager.get_all_products(account.id)

        # 3. Получаем кастомные названия
        custom_names = await product_manager.get_custom_names_dict(account.id)

        await callback.message.answer(
            f"✅ <b>Тест сохранения товаров:</b>\n\n"
            f"🏪 Магазин: {account.account_name or account.id}\n"
            f"📦 Тестовый товар: {test_product.supplier_article}\n"
            f"🔢 Всего товаров в БД: {len(all_products)}\n"
            f"📝 Кастомных названий: {len(custom_names)}\n\n"
            f"<i>Теперь запросите статистику через 'Вчера по товарам'</i>"
        )

    except Exception as e:
        await callback.message.answer(f"❌ Ошибка теста: {str(e)}")
