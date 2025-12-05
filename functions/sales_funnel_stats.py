# functions/sales_funnel_stats.py
# import aiohttp
# import asyncio
# from datetime import datetime, date, timedelta
# from typing import List, Dict, Tuple, Optional
# import logging
#
# logger = logging.getLogger(__name__)
#
#
# class SalesFunnelStatistics:
#     def __init__(self, api_key: str):
#         self.api_key = api_key
#         self.base_url = "https://seller-analytics-api.wildberries.ru"
#         self.headers = {
#             "Authorization": api_key,
#             "Content-Type": "application/json"
#         }
#         self.max_retries = 3
#         self.retry_delay = 30  # секунды
#
#     async def _make_request_with_retry(self, session: aiohttp.ClientSession,
#                                        url: str, data: Dict, attempt: int = 1) -> Optional[Dict]:
#         """Выполнить запрос с повторными попытками"""
#         try:
#             logger.info(f"Запрос к {url} (попытка {attempt}/{self.max_retries})")
#
#             async with session.post(
#                     url,
#                     headers=self.headers,
#                     json=data,
#                     timeout=30
#             ) as response:
#
#                 logger.info(f"Статус ответа: {response.status}")
#
#                 if response.status == 200:
#                     result = await response.json()
#                     logger.info(f"Успешный ответ получен, товаров: {len(result.get('data', {}).get('products', []))}")
#                     return result
#                 elif response.status == 401:
#                     logger.error("Ошибка 401: Неверный API ключ")
#                     raise ValueError("Неверный API ключ")
#                 elif response.status == 400:
#                     error_text = await response.text()
#                     logger.error(f"Ошибка 400: Неверный запрос")
#                     logger.debug(f"Детали ошибки: {error_text[:500]}")
#                     raise ValueError(f"Неверный формат запроса")
#                 elif response.status == 429:
#                     logger.warning("Превышен лимит запросов")
#                     if attempt < self.max_retries:
#                         wait_time = attempt * self.retry_delay
#                         logger.info(f"Ждем {wait_time} секунд перед повторной попыткой")
#                         await asyncio.sleep(wait_time)
#                         return await self._make_request_with_retry(session, url, data, attempt + 1)
#                     else:
#                         raise ValueError("Превышен лимит запросов после всех попыток")
#                 else:
#                     error_text = await response.text()
#                     logger.error(f"Ошибка API: {response.status}")
#                     raise ValueError(f"Ошибка сервера: {response.status}")
#
#         except asyncio.TimeoutError:
#             logger.warning(f"Таймаут запроса (попытка {attempt})")
#             if attempt < self.max_retries:
#                 await asyncio.sleep(self.retry_delay)
#                 return await self._make_request_with_retry(session, url, data, attempt + 1)
#             else:
#                 raise ValueError("Таймаут запроса после всех попыток")
#
#         except Exception as e:
#             logger.error(f"Неожиданная ошибка: {e}")
#             raise
#
#     async def get_today_sales_funnel(self) -> Dict[str, Dict[str, int]]:
#         """
#         Получить статистику по воронке продаж за сегодняшний день
#         Возвращает словарь с суммарными показателями:
#         {
#             "orders": {"count": int, "sum": float},
#             "buyouts": {"count": int, "sum": float}
#         }
#         """
#         try:
#             # Определяем периоды
#             today = date.today()
#             today_str = today.strftime("%Y-%m-%d")
#
#             # Для прошлого периода используем вчерашний день
#             yesterday = today - timedelta(days=1)
#             yesterday_str = yesterday.strftime("%Y-%m-%d")
#
#             # Формируем данные запроса
#             request_data = {
#                 "selectedPeriod": {
#                     "start": today_str,
#                     "end": today_str
#                 },
#                 "pastPeriod": {
#                     "start": yesterday_str,
#                     "end": yesterday_str
#                 },
#                 "nmIds": [],
#                 "brandNames": [],
#                 "subjectIds": [],
#                 "tagIds": [],
#                 "skipDeletedNm": False,
#                 "orderBy": {
#                     "field": "orderCount",
#                     "mode": "desc"
#                 },
#                 "limit": 1000,
#                 "offset": 0
#             }
#
#             logger.info(f"Запрос данных за сегодня: {today_str} (сравнение с вчера: {yesterday_str})")
#
#             async with aiohttp.ClientSession() as session:
#                 response_data = await self._make_request_with_retry(
#                     session,
#                     f"{self.base_url}/api/analytics/v3/sales-funnel/products",
#                     request_data
#                 )
#
#                 if not response_data or "data" not in response_data:
#                     logger.warning("Пустой ответ от API или отсутствует ключ 'data'")
#                     return {
#                         "orders": {"count": 0, "sum": 0.0},
#                         "buyouts": {"count": 0, "sum": 0.0}
#                     }
#
#                 # Суммируем показатели по всем товарам
#                 total_order_count = 0
#                 total_order_sum = 0.0
#                 total_buyout_count = 0
#                 total_buyout_sum = 0.0
#
#                 products = response_data["data"].get("products", [])
#                 logger.info(f"Получено товаров: {len(products)}")
#
#                 if not products:
#                     logger.info("Нет данных по товарам за выбранный период")
#
#                 for product_data in products:
#                     statistic = product_data.get("statistic", {}).get("selected", {})
#
#                     total_order_count += statistic.get("orderCount", 0)
#                     total_order_sum += statistic.get("orderSum", 0)
#                     total_buyout_count += statistic.get("buyoutCount", 0)
#                     total_buyout_sum += statistic.get("buyoutSum", 0)
#
#                 logger.info(f"Итого: заказов {total_order_count} шт. на {total_order_sum} руб., "
#                             f"выкупов {total_buyout_count} шт. на {total_buyout_sum} руб.")
#
#                 return {
#                     "orders": {
#                         "count": total_order_count,
#                         "sum": total_order_sum
#                     },
#                     "buyouts": {
#                         "count": total_buyout_count,
#                         "sum": total_buyout_sum
#                     }
#                 }
#
#         except ValueError as e:
#             logger.error(f"Ошибка получения данных воронки продаж: {e}")
#             raise
#
#         except Exception as e:
#             logger.error(f"Неожиданная ошибка при получении данных воронки: {e}")
#             raise ValueError(f"Ошибка получения данных: {str(e)}")
#
#     async def get_yesterday_sales_funnel(self) -> Dict[str, Dict[str, int]]:
#         """
#         Получить статистику по воронке продаж за вчерашний день
#         """
#         try:
#             # Определяем периоды
#             yesterday = date.today() - timedelta(days=1)
#             yesterday_str = yesterday.strftime("%Y-%m-%d")
#
#             # Для прошлого периода используем позавчера
#             day_before_yesterday = yesterday - timedelta(days=1)
#             day_before_yesterday_str = day_before_yesterday.strftime("%Y-%m-%d")
#
#             # Формируем данные запроса
#             request_data = {
#                 "selectedPeriod": {
#                     "start": yesterday_str,
#                     "end": yesterday_str
#                 },
#                 "pastPeriod": {
#                     "start": day_before_yesterday_str,
#                     "end": day_before_yesterday_str
#                 },
#                 "nmIds": [],
#                 "brandNames": [],
#                 "subjectIds": [],
#                 "tagIds": [],
#                 "skipDeletedNm": False,
#                 "orderBy": {
#                     "field": "orderCount",
#                     "mode": "desc"
#                 },
#                 "limit": 1000,
#                 "offset": 0
#             }
#
#             logger.info(f"Запрос данных за вчера: {yesterday_str} (сравнение с позавчера: {day_before_yesterday_str})")
#
#             async with aiohttp.ClientSession() as session:
#                 response_data = await self._make_request_with_retry(
#                     session,
#                     f"{self.base_url}/api/analytics/v3/sales-funnel/products",
#                     request_data
#                 )
#
#                 if not response_data or "data" not in response_data:
#                     logger.warning("Пустой ответ от API")
#                     return {
#                         "orders": {"count": 0, "sum": 0.0},
#                         "buyouts": {"count": 0, "sum": 0.0}
#                     }
#
#                 # Суммируем показатели по всем товарам
#                 total_order_count = 0
#                 total_order_sum = 0.0
#                 total_buyout_count = 0
#                 total_buyout_sum = 0.0
#
#                 products = response_data["data"].get("products", [])
#                 logger.info(f"Получено товаров: {len(products)}")
#
#                 for product_data in products:
#                     statistic = product_data.get("statistic", {}).get("selected", {})
#
#                     total_order_count += statistic.get("orderCount", 0)
#                     total_order_sum += statistic.get("orderSum", 0)
#                     total_buyout_count += statistic.get("buyoutCount", 0)
#                     total_buyout_sum += statistic.get("buyoutSum", 0)
#
#                 return {
#                     "orders": {
#                         "count": total_order_count,
#                         "sum": total_order_sum
#                     },
#                     "buyouts": {
#                         "count": total_buyout_count,
#                         "sum": total_buyout_sum
#                     }
#                 }
#
#         except Exception as e:
#             logger.error(f"Ошибка получения данных за вчера: {e}")
#             raise
#
#     async def get_custom_period_sales_funnel(self, selected_start: date, selected_end: date,
#                                              past_start: date, past_end: date) -> Dict[str, Dict[str, int]]:
#         """
#         Получить статистику по воронке продаж за произвольные периоды
#         """
#         try:
#             selected_start_str = selected_start.strftime("%Y-%m-%d")
#             selected_end_str = selected_end.strftime("%Y-%m-%d")
#             past_start_str = past_start.strftime("%Y-%m-%d")
#             past_end_str = past_end.strftime("%Y-%m-%d")
#
#             # Формируем данные запроса
#             request_data = {
#                 "selectedPeriod": {
#                     "start": selected_start_str,
#                     "end": selected_end_str
#                 },
#                 "pastPeriod": {
#                     "start": past_start_str,
#                     "end": past_end_str
#                 },
#                 "nmIds": [],
#                 "brandNames": [],
#                 "subjectIds": [],
#                 "tagIds": [],
#                 "skipDeletedNm": False,
#                 "orderBy": {
#                     "field": "orderCount",
#                     "mode": "desc"
#                 },
#                 "limit": 1000,
#                 "offset": 0
#             }
#
#             logger.info(f"Запрос данных: {selected_start_str}-{selected_end_str} "
#                         f"(сравнение с {past_start_str}-{past_end_str})")
#
#             async with aiohttp.ClientSession() as session:
#                 response_data = await self._make_request_with_retry(
#                     session,
#                     f"{self.base_url}/api/analytics/v3/sales-funnel/products",
#                     request_data
#                 )
#
#                 if not response_data or "data" not in response_data:
#                     logger.warning("Пустой ответ от API")
#                     return {
#                         "orders": {"count": 0, "sum": 0.0},
#                         "buyouts": {"count": 0, "sum": 0.0}
#                     }
#
#                 # Суммируем показатели по всем товарам
#                 total_order_count = 0
#                 total_order_sum = 0.0
#                 total_buyout_count = 0
#                 total_buyout_sum = 0.0
#
#                 products = response_data["data"].get("products", [])
#                 logger.info(f"Получено товаров: {len(products)}")
#
#                 for product_data in products:
#                     statistic = product_data.get("statistic", {}).get("selected", {})
#
#                     total_order_count += statistic.get("orderCount", 0)
#                     total_order_sum += statistic.get("orderSum", 0)
#                     total_buyout_count += statistic.get("buyoutCount", 0)
#                     total_buyout_sum += statistic.get("buyoutSum", 0)
#
#                 return {
#                     "orders": {
#                         "count": total_order_count,
#                         "sum": total_order_sum
#                     },
#                     "buyouts": {
#                         "count": total_buyout_count,
#                         "sum": total_buyout_sum
#                     }
#                 }
#
#         except Exception as e:
#             logger.error(f"Ошибка получения данных за период: {e}")
#             raise
