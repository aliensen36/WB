# handlers/statistics_handlers.py
import asyncio
from aiogram import Router, F
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession
from database.account_manager import AccountManager
from database.product_manager import ProductManager
from functions.product_statistics import ProductStatisticsService
from functions.wb_api import WBAPI
from keyboards.main_kb import get_main_keyboard
from datetime import datetime, timedelta
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
    Используем ТОЛЬКО API заказов (/api/v1/supplier/orders)
    """
    # Простое сообщение без редактирования
    initial_msg = await message.answer(
        "📊 <b>Собираем статистику по товарам за вчера...</b>\n"
        "🔄 Использую только API заказов...",
        reply_markup=get_main_keyboard()
    )

    try:
        from datetime import datetime, timedelta

        account_manager = AccountManager(session)
        all_accounts = await account_manager.get_all_accounts()

        if not all_accounts:
            await message.answer(
                "❌ <b>Нет добавленных магазинов</b>",
                reply_markup=get_main_keyboard()
            )
            return

        account = all_accounts[0]
        account_name = account.account_name or f"Магазин {account.id}"

        # Получаем дату вчера
        yesterday = datetime.now().date() - timedelta(days=1)
        yesterday_str = yesterday.strftime("%d.%m.%Y")

        # День недели на русском
        days = ["Понедельник", "Вторник", "Среда", "Четверг", "Пятница", "Суббота", "Воскресенье"]
        day_name = days[yesterday.weekday()]

        # Инициализируем сервисы
        product_manager = ProductManager(session)
        wb_api = WBAPI(account.api_key)
        stats_service = ProductStatisticsService(product_manager)

        # Получаем данные за ВЧЕРА ТОЛЬКО из API заказов
        orders_data = await wb_api.get_yesterday_orders_detailed()
        logger.info(f"📦 Получено заказов за {yesterday_str}: {len(orders_data)}")

        # Если нет данных
        if not orders_data:
            await message.answer(
                f"📭 <b>Нет данных за {yesterday_str}</b>\n\n"
                f"🏪 {account_name}\n"
                f"📅 {day_name}\n\n"
                f"<i>API заказов не вернул данные за этот день</i>\n"
                f"<i>Эндпоинт: /api/v1/supplier/orders</i>",
                reply_markup=get_main_keyboard()
            )
            return

        # Обрабатываем данные ТОЛЬКО из заказов
        product_stats, product_info = await stats_service.process_orders_data_only(
            seller_account_id=account.id,
            orders_data=orders_data
        )

        logger.info(f"✅ Обработано артикулов: {len(product_info['unique_articles'])}")
        logger.info(f"🆕 Новых товаров: {product_info['created']}")

        # Анализ статистики выкупов
        products_with_sales = sum(1 for stats in product_stats.values() if stats['sales_qty'] > 0)
        total_sales_qty_all = sum(stats['sales_qty'] for stats in product_stats.values())
        logger.info(f"📦 Товаров с выкупами: {products_with_sales}, всего выкуплено: {total_sales_qty_all} шт.")

        if products_with_sales == 0:
            await message.answer(
                f"📭 <b>Нет выкупленных товаров за {yesterday_str}</b>\n\n"
                f"🏪 {account_name}\n"
                f"📅 {day_name}\n\n"
                f"<i>Статистика из API заказов:</i>\n"
                f"• Всего записей заказов: {product_info['total_records']}\n"
                f"• Выкуплено (isCancel: false, isRealization: true): {product_info['realization_true']}\n"
                f"• Не выкуплено (isCancel: false, isRealization: false): {product_info['realization_false']}\n"
                f"• Отменено (isCancel: true): {product_info['cancelled']}\n"
                f"• Уникальных артикулов: {len(product_info['unique_articles'])}\n\n"
                f"<i>Эндпоинт: /api/v1/supplier/orders</i>",
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
            f"<b>Товары по этому магазину:</b>\n"
            f"<i>Данные из API заказов (/api/v1/supplier/orders)</i>\n"
        )
        report_parts.append(header)

        # Информация о методике расчета
        calculation_info = (
            f"\n<i>Методика расчета:</i>\n"
            f"• <b>Кол-во проданных (sales_qty)</b>: сумма <code>quantity</code> из записей где "
            f"<code>isCancel: false</code> И <code>isRealization: true</code>\n"
            f"• <b>Общая сумма (sales_amount)</b>: сумма <code>priceWithDisc * quantity</code> из записей где "
            f"<code>isCancel: false</code> И <code>isRealization: true</code>\n"
            f"• Игнорируются записи: <code>isCancel: true</code> (отмененные) и "
            f"<code>isRealization: false</code> (невыкупленные)\n\n"
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
            key=lambda x: x[1]['sales_amount'],
            reverse=True
        )

        for i, (article, stats) in enumerate(sorted_products, 1):
            # Пропускаем товары без выкупов
            if stats['sales_qty'] == 0 and stats['sales_amount'] == 0:
                continue

            products_with_sales_count += 1

            # Получаем название из БД
            display_name = custom_names.get(article, article)

            # Форматируем сумму
            sales_amount_formatted = f"{stats['sales_amount']:,.2f}".replace(",", " ").replace(".", ",")

            # Формируем строку для товара
            product_line = (
                f"\n<b>{i}. {display_name}</b>\n"
                f"   • Артикул WB (supplierArticle): <code>{article}</code>\n"
                f"   • Название из БД (custom_name): {display_name}\n"
                f"   • Кол-во проданных (quantity при isRealization: true): <b>{stats['sales_qty']} шт.</b>\n"
                f"   • Общая сумма (priceWithDisc * quantity): <b>{sales_amount_formatted} ₽</b>\n"
            )

            all_products_text += product_line
            total_sales_qty += stats['sales_qty']
            total_sales_amount += stats['sales_amount']

        # Формируем итоги
        total_amount_formatted = f"{total_sales_amount:,.2f}".replace(",", " ").replace(".", ",")

        report_parts.append(all_products_text)

        # Итоги
        footer = (
            f"\n{'─' * 40}\n"
            f"📊 <b>ИТОГО ПО МАГАЗИНУ:</b>\n"
            f"📦 Товаров с выкупами: {products_with_sales_count}\n"
            f"📈 Общее кол-во выкупленных: <b>{total_sales_qty} шт.</b>\n"
            f"💰 Общая сумма выкупов: <b>{total_amount_formatted} ₽</b>\n"
        )
        report_parts.append(footer)

        # Детальная статистика API
        detail_stats = (
            f"\n<i>Детальная статистика API заказов:</i>\n"
            f"• Всего записей заказов: {product_info['total_records']}\n"
            f"• Обработано записей: {product_info['records_processed']}\n"
            f"• Выкуплено (isCancel: false, isRealization: true): {product_info['realization_true']}\n"
            f"• Не выкуплено (isCancel: false, isRealization: false): {product_info['realization_false']}\n"
            f"• Отменено (isCancel: true): {product_info['cancelled']}\n"
            f"• Уникальных артикулов: {len(product_info['unique_articles'])}\n"
            f"• Новых товаров: {product_info['created']}\n\n"
            f"<i>Использованные поля API заказов:</i>\n"
            f"• Для артикула: <code>supplierArticle</code>\n"
            f"• Для количества: <code>quantity</code> (при isCancel: false и isRealization: true)\n"
            f"• Для суммы: <code>priceWithDisc * quantity</code>\n"
            f"• Для фильтрации выкупов: <code>isCancel: false</code> И <code>isRealization: true</code>\n"
            f"• Эндпоинт: <code>/api/v1/supplier/orders</code> с параметром <code>flag=1</code>"
        )
        report_parts.append(detail_stats)

        # Отправляем отчет
        full_report = "".join(report_parts)

        # Разбиваем на части если слишком длинный
        if len(full_report) > 4000:
            # Отправляем первую часть
            first_part = header + calculation_info + all_products_text[:1800]
            await message.answer(first_part, parse_mode='HTML', reply_markup=get_main_keyboard())

            # Отправляем оставшуюся часть
            remaining_part = all_products_text[1800:] + footer + detail_stats
            await message.answer(remaining_part, parse_mode='HTML', reply_markup=get_main_keyboard())
        else:
            await message.answer(full_report, parse_mode='HTML', reply_markup=get_main_keyboard())

    except Exception as e:
        logger.error(f"❌ Ошибка при сборе статистики по товарам за вчера: {e}", exc_info=True)

        error_msg = (
            f"❌ <b>Ошибка при сборе статистики</b>\n\n"
            f"<code>{str(e)[:200]}</code>\n\n"
            f"<i>Проверьте логи для подробностей</i>\n"
            f"<i>Использован эндпоинт: /api/v1/supplier/orders</i>"
        )

        await message.answer(error_msg, parse_mode='HTML', reply_markup=get_main_keyboard())
