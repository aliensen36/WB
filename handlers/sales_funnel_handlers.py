# handlers/sales_funnel_handlers.py
# import asyncio
# from aiogram.types import CallbackQuery, Message
# from aiogram import Router, F
# from datetime import datetime, date, timedelta
# import logging
# from sqlalchemy.ext.asyncio import AsyncSession
#
# from database.account_manager import AccountManager
# from functions.sales_funnel_stats import SalesFunnelStatistics
# from keyboards.statistics_kb import get_stats_keyboard
#
# logger = logging.getLogger(__name__)
#
# sales_funnel_router = Router()
#
#
# @sales_funnel_router.callback_query(F.data == "today_sales_funnel")
# async def handle_today_sales_funnel(callback: CallbackQuery, session: AsyncSession):
#     """Показать статистику воронки продаж за сегодня для всех магазинов"""
#     await callback.answer()
#
#     try:
#         loading_msg = await callback.message.answer(
#             "📊 <b>Получение статистики воронки продаж...</b>\n\n"
#             "🔄 Загружаем данные по всем магазинам...\n"
#             "<i>Сравниваем сегодня с вчерашним днем</i>"
#         )
#
#         account_manager = AccountManager(session)
#         all_accounts = await account_manager.get_all_accounts()
#
#         if not all_accounts:
#             await loading_msg.delete()
#             await callback.message.answer(
#                 "❌ <b>Нет добавленных магазинов</b>\n\n"
#                 "Перейдите в настройки, чтобы добавить первый магазин.",
#                 reply_markup=get_stats_keyboard()
#             )
#             return
#
#         today = date.today()
#         today_date = today.strftime("%d.%m.%Y")
#
#         stats_text = f"📊 <b>Воронка продаж</b>\n\n"
#         stats_text += f"📅 <b>Текущий период:</b> {today_date}\n\n"
#
#         successful_accounts = 0
#         failed_accounts = 0
#
#         # Общие суммарные показатели
#         total_all_orders = 0
#         total_all_orders_sum = 0.0
#         total_all_buyouts = 0
#         total_all_buyouts_sum = 0.0
#
#         # Собираем статистику по каждому магазину
#         for i, account in enumerate(all_accounts):
#             account_display_name = account.account_name or f"Магазин {account.id}"
#
#             try:
#                 # Задержка между запросами к разным аккаунтам
#                 if i > 0:
#                     await asyncio.sleep(5)  # Увеличил задержку из-за ограничений API
#
#                 wb_api = SalesFunnelStatistics(account.api_key)
#                 stats = await wb_api.get_today_sales_funnel()
#
#                 orders = stats["orders"]
#                 buyouts = stats["buyouts"]
#
#                 # Форматируем суммы
#                 formatted_orders_sum = f"{orders['sum']:,.0f} ₽".replace(",", " ").replace(".", ",")
#                 formatted_buyouts_sum = f"{buyouts['sum']:,.0f} ₽".replace(",", " ").replace(".", ",")
#
#                 # Добавляем в общие суммы
#                 total_all_orders += orders['count']
#                 total_all_orders_sum += orders['sum']
#                 total_all_buyouts += buyouts['count']
#                 total_all_buyouts_sum += buyouts['sum']
#
#                 stats_text += f"<b>🏪 {account_display_name}</b>\n"
#                 stats_text += f"   🛒 <b>Заказали:</b> {orders['count']} шт. на {formatted_orders_sum}\n"
#                 stats_text += f"   ✅ <b>Выкупили:</b> {buyouts['count']} шт. на {formatted_buyouts_sum}\n\n"
#
#                 successful_accounts += 1
#
#             except Exception as e:
#                 error_message = str(e)
#
#                 # Определяем тип ошибки
#                 if "Неверный API ключ" in error_message:
#                     display_error = "❌ Неверный API ключ"
#                 elif "Превышен лимит запросов" in error_message:
#                     display_error = "⏳ Превышен лимит запросов"
#                 elif "Таймаут" in error_message:
#                     display_error = "⌛ Таймаут запроса"
#                 elif "Неверный формат запроса" in error_message:
#                     # Возможно, API не отдает данные за сегодня (слишком свежие данные)
#                     display_error = "📅 Данные за сегодня еще не доступны"
#                 elif "Ошибка сервера" in error_message:
#                     display_error = "🔧 Ошибка сервера"
#                 else:
#                     display_error = "🔌 Ошибка подключения"
#
#                 stats_text += f"<b>🏪 {account_display_name}</b>\n"
#                 stats_text += f"   {display_error}\n\n"
#                 failed_accounts += 1
#
#                 logger.warning(f"Ошибка для {account_display_name}: {error_message}")
#
#         if failed_accounts > 0:
#             stats_text += f"\n💡 <i>Если данные за сегодня еще не доступны, попробуйте запросить статистику за вчера.</i>"
#
#         await loading_msg.delete()
#         await callback.message.answer(stats_text, reply_markup=get_stats_keyboard())
#
#     except Exception as e:
#         logger.error(f"Неожиданная ошибка в обработчике воронки продаж: {e}", exc_info=True)
#         try:
#             await loading_msg.delete()
#         except:
#             pass
#         await callback.message.answer(
#             "❌ <b>Произошла непредвиденная ошибка</b>\n\n"
#             "<i>Попробуйте позже или используйте стандартную статистику</i>",
#             reply_markup=get_stats_keyboard()
#         )
#
#
# @sales_funnel_router.callback_query(F.data == "yesterday_sales_funnel")
# async def handle_yesterday_sales_funnel(callback: CallbackQuery, session: AsyncSession):
#     """Показать статистику воронки продаж за вчера для всех магазинов"""
#     await callback.answer()
#
#     try:
#         loading_msg = await callback.message.answer(
#             "📊 <b>Получение статистики воронки продаж за вчера...</b>\n\n"
#             "🔄 Загружаем данные по всем магазинам..."
#         )
#
#         account_manager = AccountManager(session)
#         all_accounts = await account_manager.get_all_accounts()
#
#         if not all_accounts:
#             await loading_msg.delete()
#             await callback.message.answer(
#                 "❌ <b>Нет добавленных магазинов</b>",
#                 reply_markup=get_stats_keyboard()
#             )
#             return
#
#         yesterday = date.today() - timedelta(days=1)
#         day_before = yesterday - timedelta(days=1)
#
#         yesterday_date = yesterday.strftime("%d.%m.%Y")
#         day_before_date = day_before.strftime("%d.%m.%Y")
#
#         stats_text = f"📊 <b>Воронка продаж</b>\n\n"
#         stats_text += f"📅 <b>Текущий период:</b> {yesterday_date}\n\n"
#
#         successful_accounts = 0
#
#         # Общие суммарные показатели
#         total_all_orders = 0
#         total_all_orders_sum = 0.0
#         total_all_buyouts = 0
#         total_all_buyouts_sum = 0.0
#
#         for i, account in enumerate(all_accounts):
#             account_display_name = account.account_name or f"Магазин {account.id}"
#
#             try:
#                 if i > 0:
#                     await asyncio.sleep(5)
#
#                 wb_api = SalesFunnelStatistics(account.api_key)
#                 stats = await wb_api.get_yesterday_sales_funnel()
#
#                 orders = stats["orders"]
#                 buyouts = stats["buyouts"]
#
#                 formatted_orders_sum = f"{orders['sum']:,.0f} ₽".replace(",", " ").replace(".", ",")
#                 formatted_buyouts_sum = f"{buyouts['sum']:,.0f} ₽".replace(",", " ").replace(".", ",")
#
#                 # Добавляем в общие суммы
#                 total_all_orders += orders['count']
#                 total_all_orders_sum += orders['sum']
#                 total_all_buyouts += buyouts['count']
#                 total_all_buyouts_sum += buyouts['sum']
#
#                 stats_text += f"<b>🏪 {account_display_name}</b>\n"
#                 stats_text += f"   🛒 <b>Заказали:</b> {orders['count']} шт. на {formatted_orders_sum}\n"
#                 stats_text += f"   ✅ <b>Выкупили:</b> {buyouts['count']} шт. на {formatted_buyouts_sum}\n\n"
#
#                 successful_accounts += 1
#
#             except Exception as e:
#                 error_message = str(e)
#                 display_error = "🔌 Ошибка подключения"
#
#                 if "Неверный API ключ" in error_message:
#                     display_error = "❌ Неверный API ключ"
#                 elif "Неверный формат запроса" in error_message:
#                     display_error = "📝 Ошибка запроса"
#
#                 stats_text += f"<b>🏪 {account_display_name}</b>\n"
#                 stats_text += f"   {display_error}\n\n"
#
#                 logger.warning(f"Ошибка для {account_display_name}: {error_message}")
#
#         await loading_msg.delete()
#
#         if successful_accounts == 0:
#             stats_text = "❌ <b>Не удалось получить данные ни по одному магазину</b>"
#
#         await callback.message.answer(stats_text, reply_markup=get_stats_keyboard())
#
#     except Exception as e:
#         logger.error(f"Ошибка в обработчике вчерашней статистики: {e}")
#         try:
#             await loading_msg.delete()
#         except:
#             pass
#         await callback.message.answer(
#             "❌ <b>Произошла ошибка</b>",
#             reply_markup=get_stats_keyboard()
#         )
#
#
# @sales_funnel_router.callback_query(F.data == "test_sales_funnel")
# async def handle_test_sales_funnel(callback: CallbackQuery, session: AsyncSession):
#     """Тестовый запрос - получить данные за вчера (более надежно)"""
#     await callback.answer()
#
#     try:
#         loading_msg = await callback.message.answer(
#             "🧪 <b>Тестовый запрос воронки продаж...</b>\n\n"
#             "Пробуем получить данные за вчерашний день"
#         )
#
#         account_manager = AccountManager(session)
#         accounts = await account_manager.get_all_accounts()
#
#         if not accounts:
#             await loading_msg.delete()
#             await callback.message.answer("Нет аккаунтов")
#             return
#
#         # Берем первый аккаунт для теста
#         account = accounts[0]
#         wb_api = SalesFunnelStatistics(account.api_key)
#
#         try:
#             # Пробуем получить данные за вчера
#             stats = await wb_api.get_yesterday_sales_funnel()
#
#             orders = stats["orders"]
#             buyouts = stats["buyouts"]
#
#             formatted_orders_sum = f"{orders['sum']:,.0f} ₽".replace(",", " ").replace(".", ",")
#             formatted_buyouts_sum = f"{buyouts['sum']:,.0f} ₽".replace(",", " ").replace(".", ",")
#
#             result_text = f"✅ <b>Тестовый запрос успешен!</b>\n\n"
#             result_text += f"<b>Аккаунт:</b> {account.account_name or account.id}\n\n"
#             result_text += f"<b>Данные за вчера:</b>\n"
#             result_text += f"   🛒 Заказали: {orders['count']} шт. на {formatted_orders_sum}\n"
#             result_text += f"   ✅ Выкупили: {buyouts['count']} шт. на {formatted_buyouts_sum}\n\n"
#             result_text += f"<i>API работает корректно.</i>"
#
#         except Exception as e:
#             result_text = f"❌ <b>Тестовый запрос не удался</b>\n\n"
#             result_text += f"<b>Ошибка:</b> {str(e)[:200]}\n\n"
#             result_text += f"<i>Проверьте API ключ и лимиты запросов.</i>"
#
#         await loading_msg.delete()
#         await callback.message.answer(result_text, reply_markup=get_stats_keyboard())
#
#     except Exception as e:
#         logger.error(f"Ошибка в тестовом запросе: {e}")
#         try:
#             await loading_msg.delete()
#         except:
#             pass
#         await callback.message.answer("❌ Ошибка тестового запроса")
