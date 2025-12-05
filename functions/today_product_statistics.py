# functions/today_product_statistics.py
# import aiohttp
# import asyncio
# from datetime import datetime, timedelta
# from typing import List, Dict, Tuple, Optional
# import logging
# from functools import wraps
#
# logger = logging.getLogger(__name__)
#
#
# class TodayProductStatistics:
#     def __init__(self, api_key: str):
#         """
#         Инициализация статистики для сегодня
#
#         Args:
#             api_key: API ключ WB (должен передаваться извне, например из БД)
#         """
#         self.api_key = api_key
#         self.base_url = "https://seller-analytics-api.wildberries.ru"
#         self.headers = {
#             "Authorization": f"Bearer {api_key}",
#             "Content-Type": "application/json",
#             "accept": "application/json"
#         }
#
#     def _retry_decorator(max_retries: int = 5, initial_delay: int = 30):
#         """Декоратор для повторных попыток"""
#
#         def decorator(func):
#             @wraps(func)
#             async def wrapper(self, *args, **kwargs):
#                 last_error = None
#
#                 for attempt in range(max_retries):
#                     try:
#                         return await func(self, *args, **kwargs)
#
#                     except asyncio.TimeoutError:
#                         logger.warning(f"Таймаут запроса {func.__name__} (попытка {attempt + 1}/{max_retries})")
#                         last_error = "Таймаут запроса"
#                         if attempt < max_retries - 1:
#                             wait_time = initial_delay * (attempt + 1)
#                             logger.info(f"Ждем {wait_time} секунд перед повторной попыткой")
#                             await asyncio.sleep(wait_time)
#                             continue
#                         else:
#                             raise ValueError("Таймаут запроса")
#
#                     except aiohttp.ClientResponseError as e:
#                         if e.status == 401:
#                             logger.error("Ошибка 401: Неверный API ключ")
#                             raise ValueError("Неверный API ключ")
#                         elif e.status == 429:
#                             logger.warning(f"Превышен лимит запросов (попытка {attempt + 1})")
#                             last_error = "Превышен лимит запросов"
#                             wait_time = initial_delay * (attempt + 1)
#                             logger.info(f"Ждем {wait_time} секунд перед повторной попыткой")
#                             await asyncio.sleep(wait_time)
#                             continue
#                         else:
#                             logger.error(f"Ошибка API: {e.status}")
#                             last_error = f"Ошибка сервера: {e.status}"
#                             if attempt < max_retries - 1:
#                                 await asyncio.sleep(30)
#                                 continue
#                             else:
#                                 raise ValueError(f"Ошибка сервера: {e.status}")
#
#                     except Exception as e:
#                         error_msg = str(e)
#                         if "Неверный API ключ" in error_msg:
#                             raise
#                         logger.warning(
#                             f"Неожиданная ошибка при выполнении {func.__name__} (попытка {attempt + 1}): {e}")
#                         last_error = "Ошибка подключения"
#                         if attempt < max_retries - 1:
#                             await asyncio.sleep(30)
#                             continue
#                         else:
#                             raise ValueError("Ошибка подключения")
#
#                 # Если дошли досюда - все попытки исчерпаны
#                 raise ValueError(last_error or "Не удалось получить данные после всех попыток")
#
#             return wrapper
#
#         return decorator
#
#     def _get_today_date(self) -> tuple:
#         """Получить дату сегодняшнего дня с 00:00 до текущего времени"""
#         today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
#         date_str_dd_mm_yyyy = today.strftime("%d.%m.%Y")
#         date_str_yyyy_mm_dd = today.strftime("%Y-%m-%d")
#         return date_str_dd_mm_yyyy, date_str_yyyy_mm_dd, today
#
#     def _prepare_today_payload(self, limit: int = 1000, offset: int = 0) -> Dict:
#         """Подготовить payload для запроса API воронки продаж на сегодня"""
#         # Получаем даты
#         today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
#         week_ago = today - timedelta(days=7)
#
#         payload = {
#             "selectedPeriod": {
#                 "start": today.strftime("%Y-%m-%d"),
#                 "end": today.strftime("%Y-%m-%d")  # Сегодняшняя дата
#             },
#             "pastPeriod": {
#                 "start": week_ago.strftime("%Y-%m-%d"),
#                 "end": (today - timedelta(days=1)).strftime("%Y-%m-%d")  # Вчера
#             },
#             "nmIds": [],  # Все товары
#             "brandNames": [],  # Все бренды
#             "subjectIds": [],  # Все категории
#             "tagIds": [],  # Все теги
#             "skipDeletedNm": False,
#             "orderBy": {
#                 "field": "openCard",  # Сортировка по просмотрам
#                 "mode": "desc"
#             },
#             "limit": min(limit, 1000),
#             "offset": offset
#         }
#         return payload
#
#     @_retry_decorator(max_retries=3, initial_delay=20)
#     async def _make_request(self, payload: Dict) -> Optional[Dict]:
#         """Выполнить запрос к API воронке продаж"""
#         url = f"{self.base_url}/api/analytics/v3/sales-funnel/products"
#
#         async with aiohttp.ClientSession() as session:
#             async with session.post(
#                     url,
#                     headers=self.headers,
#                     json=payload,
#                     timeout=60
#             ) as response:
#
#                 if response.status == 200:
#                     data = await response.json()
#                     return data
#                 elif response.status == 401:
#                     raise aiohttp.ClientResponseError(
#                         request_info=None,
#                         history=None,
#                         status=401,
#                         message="Неверный API ключ"
#                     )
#                 elif response.status == 429:
#                     raise aiohttp.ClientResponseError(
#                         request_info=None,
#                         history=None,
#                         status=429,
#                         message="Превышен лимит запросов"
#                     )
#                 else:
#                     raise aiohttp.ClientResponseError(
#                         request_info=None,
#                         history=None,
#                         status=response.status,
#                         message=f"Ошибка сервера: {response.status}"
#                     )
#
#     async def get_today_sales_funnel_data(self, batch_size: int = 500) -> tuple:
#         """
#         Получить ВСЕ данные по воронке продаж за сегодня с пагинацией
#         """
#         date_str_dd_mm_yyyy, date_str_yyyy_mm_dd, today_date = self._get_today_date()
#
#         all_products = []
#         offset = 0
#         page = 1
#
#         logger.info(f"Начало извлечения данных по товарам за сегодня ({date_str_dd_mm_yyyy})")
#
#         while True:
#             logger.info(f"Запрос страницы {page}, offset: {offset}")
#
#             # Подготовка payload для сегодня
#             payload = self._prepare_today_payload(limit=batch_size, offset=offset)
#
#             # Выполнение запроса
#             data = await self._make_request(payload)
#
#             if not data:
#                 logger.warning(f"Не удалось получить данные для страницы {page}")
#                 break
#
#             # Извлечение продуктов из ответа
#             products = []
#             if "data" in data and "products" in data["data"]:
#                 products = data["data"]["products"]
#             elif "products" in data:
#                 products = data["products"]
#             else:
#                 logger.warning(f"Неожиданная структура ответа: {list(data.keys())}")
#                 break
#
#             if not products:
#                 logger.info("Больше нет данных (пустой массив продуктов)")
#                 break
#
#             # Добавление продуктов в общий список
#             all_products.extend(products)
#             logger.info(f"Страница {page}: получено {len(products)} записей, всего {len(all_products)}")
#
#             # Проверка на последнюю страницу
#             if len(products) < batch_size:
#                 logger.info(f"Это последняя страница. Всего записей: {len(all_products)}")
#                 break
#
#             # Пагинация
#             offset += batch_size
#             page += 1
#
#             # Задержка для соблюдения лимитов API
#             await asyncio.sleep(20)
#
#         logger.info(f"Извлечение завершено. Всего получено записей за сегодня: {len(all_products)}")
#         return all_products, date_str_dd_mm_yyyy, date_str_yyyy_mm_dd
#
#     async def get_today_product_stats_summary(self) -> Dict[str, any]:
#         """
#         Получить СУММАРНУЮ статистику по товарам за сегодня
#         Только общее количество и сумма по заказам и выкупам
#         """
#         try:
#             # Получаем данные
#             all_data, date_str_dd_mm_yyyy, date_str_yyyy_mm_dd = await self.get_today_sales_funnel_data()
#
#             if not all_data:
#                 logger.info("Нет данных по товарам за сегодня")
#                 return {
#                     "date": date_str_dd_mm_yyyy,
#                     "has_data": False,
#                     "total_products": 0,
#                     "total_orders": 0,
#                     "total_order_sum": 0.0,
#                     "total_buyouts": 0,
#                     "total_buyout_sum": 0.0
#                 }
#
#             # Рассчитываем суммарные показатели
#             total_orders = 0
#             total_order_sum = 0.0
#             total_buyouts = 0
#             total_buyout_sum = 0.0
#
#             for item in all_data:
#                 statistic = item.get("statistic", {}).get("selected", {})
#
#                 # Заказы
#                 orders = statistic.get("orderCount", 0)
#                 order_sum = statistic.get("orderSum", 0)
#
#                 # Выкупы
#                 buyouts = statistic.get("buyoutCount", 0)
#                 buyout_sum = statistic.get("buyoutSum", 0)
#
#                 # Суммируем
#                 total_orders += orders
#                 total_order_sum += order_sum
#                 total_buyouts += buyouts
#                 total_buyout_sum += buyout_sum
#
#             logger.info(f"Обработано товаров: {len(all_data)}")
#             logger.info(f"Суммарные заказы: {total_orders} на сумму {total_order_sum:.2f} р.")
#             logger.info(f"Суммарные выкупы: {total_buyouts} на сумму {total_buyout_sum:.2f} р.")
#
#             return {
#                 "date": date_str_dd_mm_yyyy,
#                 "has_data": True,
#                 "total_products": len(all_data),
#                 "total_orders": total_orders,
#                 "total_order_sum": total_order_sum,
#                 "total_buyouts": total_buyouts,
#                 "total_buyout_sum": total_buyout_sum,
#                 "timestamp": datetime.now().isoformat(),
#                 "period": f"с 00:00 до {datetime.now().strftime('%H:%M')}"
#             }
#
#         except Exception as e:
#             logger.error(f"Ошибка при получении суммарной статистики за сегодня: {e}")
#             return {
#                 "date": datetime.now().strftime("%d.%m.%Y"),
#                 "has_data": False,
#                 "error": str(e),
#                 "timestamp": datetime.now().isoformat()
#             }
#
#     async def get_today_detailed_stats(self) -> Dict[str, any]:
#         """
#         Получить детализированную статистику по товарам за сегодня
#         (аналогично get_yesterday_product_stats, но для сегодня)
#         """
#         try:
#             # Получаем данные
#             all_data, date_str_dd_mm_yyyy, date_str_yyyy_mm_dd = await self.get_today_sales_funnel_data()
#
#             if not all_data:
#                 logger.info("Нет данных по товарам за сегодня")
#                 return {
#                     "date": date_str_dd_mm_yyyy,
#                     "total_products": 0,
#                     "total_views": 0,
#                     "total_carts": 0,
#                     "total_orders": 0,
#                     "total_order_sum": 0.0,
#                     "total_buyouts": 0,
#                     "total_buyout_sum": 0.0,
#                     "active_products": 0,
#                     "products_with_sales": 0,
#                     "products": [],
#                     "all_products": []
#                 }
#
#             # Рассчитываем полную статистику
#             product_stats = {}
#             total_views = 0
#             total_carts = 0
#             total_orders = 0
#             total_order_sum = 0.0
#             total_buyouts = 0
#             total_buyout_sum = 0.0
#             active_products = 0
#             products_with_sales = 0
#
#             for item in all_data:
#                 product = item.get("product", {})
#                 statistic = item.get("statistic", {}).get("selected", {})
#
#                 nm_id = product.get("nmId")
#                 vendor_code = product.get("vendorCode", "")
#                 title = product.get("title", "")
#                 brand = product.get("brandName", "")
#                 category = product.get("subjectName", "")
#
#                 # Статистика
#                 views = statistic.get("openCount", 0)
#                 carts = statistic.get("cartCount", 0)
#                 orders = statistic.get("orderCount", 0)
#                 order_sum = statistic.get("orderSum", 0)
#                 buyouts = statistic.get("buyoutCount", 0)
#                 buyout_sum = statistic.get("buyoutSum", 0)
#
#                 # Проверяем активность
#                 has_activity = views > 0 or carts > 0 or orders > 0
#                 has_sales = orders > 0 or buyouts > 0
#
#                 if has_activity:
#                     active_products += 1
#                 if has_sales:
#                     products_with_sales += 1
#
#                 # Используем vendorCode или nmId как ключ
#                 article = vendor_code if vendor_code else str(nm_id)
#
#                 if article not in product_stats:
#                     product_stats[article] = {
#                         'nm_id': nm_id,
#                         'vendor_code': vendor_code,
#                         'title': title[:100] if title else "",
#                         'brand': brand,
#                         'category': category,
#                         'views': 0,
#                         'carts': 0,
#                         'orders': 0,
#                         'order_sum': 0.0,
#                         'buyouts': 0,
#                         'buyout_sum': 0.0,
#                         'conversion_to_cart': 0.0,
#                         'conversion_to_order': 0.0
#                     }
#
#                 # Обновляем статистику
#                 product_stats[article]['views'] += views
#                 product_stats[article]['carts'] += carts
#                 product_stats[article]['orders'] += orders
#                 product_stats[article]['order_sum'] += order_sum
#                 product_stats[article]['buyouts'] += buyouts
#                 product_stats[article]['buyout_sum'] += buyout_sum
#
#                 # Рассчитываем конверсии
#                 if views > 0:
#                     product_stats[article]['conversion_to_cart'] = (carts / views) * 100
#                 if carts > 0:
#                     product_stats[article]['conversion_to_order'] = (orders / carts) * 100
#
#                 # Общая статистика
#                 total_views += views
#                 total_carts += carts
#                 total_orders += orders
#                 total_order_sum += order_sum
#                 total_buyouts += buyouts
#                 total_buyout_sum += buyout_sum
#
#             # Сортируем товары по сумме выкупов
#             sorted_products = sorted(
#                 product_stats.items(),
#                 key=lambda x: x[1]['buyout_sum'],
#                 reverse=True
#             )
#
#             # Форматируем продукты для вывода
#             formatted_products = []
#             for article, stats in sorted_products:
#                 formatted_products.append({
#                     'article': article,
#                     'nm_id': stats['nm_id'],
#                     'title': stats['title'],
#                     'brand': stats['brand'],
#                     'category': stats['category'],
#                     'views': stats['views'],
#                     'carts': stats['carts'],
#                     'orders': stats['orders'],
#                     'order_sum': stats['order_sum'],
#                     'buyouts': stats['buyouts'],
#                     'buyout_sum': stats['buyout_sum'],
#                     'conversion_to_cart': stats['conversion_to_cart'],
#                     'conversion_to_order': stats['conversion_to_order']
#                 })
#
#             return {
#                 "date": date_str_dd_mm_yyyy,
#                 "total_products": len(all_data),
#                 "total_views": total_views,
#                 "total_carts": total_carts,
#                 "total_orders": total_orders,
#                 "total_order_sum": total_order_sum,
#                 "total_buyouts": total_buyouts,
#                 "total_buyout_sum": total_buyout_sum,
#                 "active_products": active_products,
#                 "products_with_sales": products_with_sales,
#                 "products": formatted_products[:50],  # Топ 50 для отображения
#                 "all_products": formatted_products,  # Все товары
#                 "overall_cart_conversion": (total_carts / total_views * 100) if total_views > 0 else 0,
#                 "overall_order_conversion": (total_orders / total_carts * 100) if total_carts > 0 else 0,
#                 "period": f"с 00:00 до {datetime.now().strftime('%H:%M')}",
#                 "timestamp": datetime.now().isoformat()
#             }
#
#         except Exception as e:
#             logger.error(f"Ошибка при получении детализированной статистики за сегодня: {e}")
#             raise
#
#
# # Теперь создайте хендлер, аналогичный тому, что есть для yesterday_stats
# # Вот пример хендлера для сегодняшней статистики:
#
# # handlers/today_product_statistics_handlers.py
# """
# from aiogram import Router, F
# from aiogram.types import CallbackQuery
# from sqlalchemy.ext.asyncio import AsyncSession
# from database.account_manager import AccountManager
# from functions.today_product_statistics import TodayProductStatistics
# from keyboards.statistics_kb import get_stats_keyboard
#
# today_stats_router = Router()
#
# @today_stats_router.callback_query(F.data == "today_stats_summary")
# async def handle_today_stats_summary(callback: CallbackQuery, session: AsyncSession):
#     Показать суммарную статистику по заказам и выкупам за сегодня
#
#     await callback.answer()
#
#     try:
#         loading_msg = await callback.message.answer(
#             "Получение суммарной статистики за сегодня..."
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
#         # Получаем дату сегодняшнего дня
#         today_date_obj = datetime.now()
#         date_str = today_date_obj.strftime("%d.%m.%Y")
#         current_time = today_date_obj.strftime("%H:%M")
#
#         await loading_msg.delete()
#
#         header_text = f"<b>📊 СУММАРНАЯ СТАТИСТИКА ЗА СЕГОДНЯ</b>\n"
#         header_text += f"Дата: {date_str}\n"
#         header_text += f"Период: с 00:00 до {current_time}\n"
#         header_text += f"Всего магазинов: {len(all_accounts)}\n\n"
#
#         await callback.message.answer(header_text)
#
#         successful_accounts = 0
#         total_all_orders = 0
#         total_all_order_sum = 0.0
#         total_all_buyouts = 0
#         total_all_buyout_sum = 0.0
#
#         # Обрабатываем КАЖДЫЙ магазин отдельно
#         for account_index, account in enumerate(all_accounts, 1):
#             account_name = account.account_name or f"Магазин {account.id}"
#
#             try:
#                 # Получаем суммарную статистику за сегодня для текущего магазина
#                 today_stats = TodayProductStatistics(account.api_key)
#                 stats = await today_stats.get_today_product_stats_summary()
#
#                 if stats["has_data"]:
#                     await callback.message.answer(
#                         f"<b>🏪 {account_name}</b>\n"
#                         f"Товаров: {stats['total_products']:,}\n"
#                         f"Заказы: {stats['total_orders']:,} шт. на {stats['total_order_sum']:.2f} ₽\n"
#                         f"Выкупы: {stats['total_buyouts']:,} шт. на {stats['total_buyout_sum']:.2f} ₽"
#                     )
#
#                     # Суммируем для общего итога
#                     total_all_orders += stats['total_orders']
#                     total_all_order_sum += stats['total_order_sum']
#                     total_all_buyouts += stats['total_buyouts']
#                     total_all_buyout_sum += stats['total_buyout_sum']
#
#                     successful_accounts += 1
#                 else:
#                     await callback.message.answer(
#                         f"<b>🏪 {account_name}</b>\n"
#                         f"Нет данных за сегодня"
#                     )
#
#             except Exception as e:
#                 error_message = str(e)
#                 if "Неверный API ключ" in error_message:
#                     display_error = "Неверный API ключ"
#                 else:
#                     display_error = "Ошибка API"
#
#                 await callback.message.answer(
#                     f"<b>🏪 {account_name}</b>\n"
#                     f"Ошибка: {display_error}"
#                 )
#
#             # Задержка между запросами к разным магазинам
#             if account_index < len(all_accounts):
#                 await asyncio.sleep(5)
#
#         # Финальное сообщение с общим итогом
#         if successful_accounts > 0:
#             final_text = "<b>📊 ОБЩИЙ ИТОГ ПО ВСЕМ МАГАЗИНАМ</b>\n\n"
#             final_text += f"Успешно обработано: {successful_accounts} из {len(all_accounts)} магазинов\n\n"
#             final_text += f"<b>Общие заказы:</b> {total_all_orders:,} шт.\n"
#             final_text += f"<b>На сумму:</b> {total_all_order_sum:.2f} ₽\n\n"
#             final_text += f"<b>Общие выкупы:</b> {total_all_buyouts:,} шт.\n"
#             final_text += f"<b>На сумму:</b> {total_all_buyout_sum:.2f} ₽"
#         else:
#             final_text = "Не удалось получить данные ни по одному магазину"
#
#         await callback.message.answer(
#             final_text,
#             reply_markup=get_stats_keyboard()
#         )
#
#     except Exception as e:
#         logger.error(f"Ошибка при получении сегодняшней статистики: {e}")
#         await callback.message.answer(
#             f"<b>Произошла ошибка:</b> {str(e)[:100]}",
#             reply_markup=get_stats_keyboard()
#         )
# """
#
#
# # Для тестирования (если запускать напрямую):
# async def test_main():
#     """Для тестирования - здесь нужно указать реальный API ключ или получить его из БД"""
#     # В реальном использовании API ключ должен приходить из хендлера
#     API_KEY = "ваш_тестовый_api_ключ"
#
#     if API_KEY == "ваш_тестовый_api_ключ":
#         print("Пожалуйста, укажите реальный API ключ для тестирования")
#         return
#
#     stats = TodayProductStatistics(API_KEY)
#
#     try:
#         summary = await stats.get_today_product_stats_summary()
#
#         if summary.get('has_data', False):
#             print(f"Дата: {summary['date']}")
#             print(f"Период: {summary.get('period', 'сегодня')}")
#             print(f"Всего товаров: {summary['total_products']}")
#             print(f"Заказы: {summary['total_orders']} шт. на сумму {summary['total_order_sum']:.2f} ₽")
#             print(f"Выкупы: {summary['total_buyouts']} шт. на сумму {summary['total_buyout_sum']:.2f} ₽")
#         else:
#             print(f"Нет данных: {summary.get('error', 'Неизвестная ошибка')}")
#
#     except Exception as e:
#         print(f"Ошибка: {e}")
#
#
# if __name__ == "__main__":
#     # Настройка логирования
#     logging.basicConfig(
#         level=logging.INFO,
#         format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
#     )
#
#     # Для тестирования раскомментируйте следующую строку и укажите API ключ
#     # asyncio.run(test_main())
#
#     print("Этот модуль предназначен для импорта, а не для прямого запуска.")
#     print("API ключ должен передаваться из хендлера, где он берется из базы данных.")