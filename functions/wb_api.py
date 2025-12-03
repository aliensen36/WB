# functions/wb_api.py
import aiohttp
import asyncio
from datetime import datetime, date, timedelta
from typing import List, Dict, Optional, Tuple
import logging

logger = logging.getLogger(__name__)


class WBAPI:
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://statistics-api.wildberries.ru"
        self.headers = {
            "Authorization": api_key,
            "Content-Type": "application/json"
        }

    async def get_today_orders_stats(self, max_retries: int = 5) -> Tuple[int, float]:
        """
        Получить статистику заказов за сегодня с повторными попытками
        """
        last_error = None

        for attempt in range(max_retries):
            try:
                today = datetime.now().date()
                date_from = today.isoformat()

                params = {
                    "dateFrom": date_from,
                    "flag": 1
                }

                logger.info(f"Запрос заказов (попытка {attempt + 1}/{max_retries})")

                async with aiohttp.ClientSession() as session:
                    async with session.get(
                            f"{self.base_url}/api/v1/supplier/orders",
                            headers=self.headers,
                            params=params,
                            timeout=30
                    ) as response:

                        logger.info(f"Статус ответа заказов: {response.status}")

                        if response.status == 200:
                            orders = await response.json()
                            logger.info(f"Успешно получено заказов: {len(orders)}")
                            return self._calculate_orders_stats(orders)

                        elif response.status == 401:
                            logger.error("Ошибка 401: Неверный API ключ")
                            raise ValueError("Неверный API ключ")

                        elif response.status == 429:
                            logger.warning(f"Превышен лимит запросов (попытка {attempt + 1})")
                            last_error = "Превышен лимит запросов"
                            # Увеличиваем задержку с каждой попыткой
                            wait_time = (attempt + 1) * 30  # 30, 60, 90, 120, 150 секунд
                            logger.info(f"Ждем {wait_time} секунд перед повторной попыткой")
                            await asyncio.sleep(wait_time)
                            continue

                        else:
                            error_text = await response.text()
                            logger.error(f"Ошибка API заказов: {response.status}")
                            last_error = "Ошибка сервера"
                            if attempt < max_retries - 1:
                                await asyncio.sleep(30)
                                continue
                            else:
                                raise ValueError("Ошибка сервера")

            except asyncio.TimeoutError:
                logger.warning(f"Таймаут запроса заказов (попытка {attempt + 1})")
                last_error = "Таймаут запроса"
                if attempt < max_retries - 1:
                    await asyncio.sleep(30)
                    continue
                else:
                    raise ValueError("Таймаут запроса")

            except ValueError as e:
                error_msg = str(e)
                # Если это неисправимые ошибки - не повторяем
                if error_msg in ["Неверный API ключ"]:
                    raise
                last_error = error_msg
                if attempt < max_retries - 1:
                    await asyncio.sleep(30)
                    continue
                else:
                    raise

            except Exception as e:
                logger.warning(f"Неожиданная ошибка при получении заказов (попытка {attempt + 1}): {e}")
                last_error = "Ошибка подключения"
                if attempt < max_retries - 1:
                    await asyncio.sleep(30)
                    continue
                else:
                    raise ValueError("Ошибка подключения")

        # Если дошли досюда - все попытки исчерпаны
        raise ValueError(last_error or "Не удалось получить данные после всех попыток")

    async def get_today_sales_stats(self, max_retries: int = 5) -> Tuple[int, float]:
        """
        Получить статистику продаж за сегодня с повторными попытками
        """
        last_error = None

        for attempt in range(max_retries):
            try:
                today = datetime.now().date()
                date_from = today.isoformat()

                params = {
                    "dateFrom": date_from,
                    "flag": 1
                }

                logger.info(f"Запрос продаж (попытка {attempt + 1}/{max_retries})")

                async with aiohttp.ClientSession() as session:
                    async with session.get(
                            f"{self.base_url}/api/v1/supplier/sales",
                            headers=self.headers,
                            params=params,
                            timeout=30
                    ) as response:

                        logger.info(f"Статус ответа продаж: {response.status}")

                        if response.status == 200:
                            sales = await response.json()
                            logger.info(f"Успешно получено продаж: {len(sales)}")
                            return self._calculate_sales_stats(sales)

                        elif response.status == 401:
                            logger.error("Ошибка 401: Неверный API ключ")
                            raise ValueError("Неверный API ключ")

                        elif response.status == 429:
                            logger.warning(f"Превышен лимит запросов (попытка {attempt + 1})")
                            last_error = "Превышен лимит запросов"
                            wait_time = (attempt + 1) * 30
                            logger.info(f"Ждем {wait_time} секунд перед повторной попыткой")
                            await asyncio.sleep(wait_time)
                            continue

                        else:
                            error_text = await response.text()
                            logger.error(f"Ошибка API продаж: {response.status}")
                            last_error = "Ошибка сервера"
                            if attempt < max_retries - 1:
                                await asyncio.sleep(30)
                                continue
                            else:
                                raise ValueError("Ошибка сервера")

            except asyncio.TimeoutError:
                logger.warning(f"Таймаут запроса продаж (попытка {attempt + 1})")
                last_error = "Таймаут запроса"
                if attempt < max_retries - 1:
                    await asyncio.sleep(30)
                    continue
                else:
                    raise ValueError("Таймаут запроса")

            except ValueError as e:
                error_msg = str(e)
                if error_msg in ["Неверный API ключ"]:
                    raise
                last_error = error_msg
                if attempt < max_retries - 1:
                    await asyncio.sleep(30)
                    continue
                else:
                    raise

            except Exception as e:
                logger.warning(f"Неожиданная ошибка при получении продаж (попытка {attempt + 1}): {e}")
                last_error = "Ошибка подключения"
                if attempt < max_retries - 1:
                    await asyncio.sleep(30)
                    continue
                else:
                    raise ValueError("Ошибка подключения")

        raise ValueError(last_error or "Не удалось получить данные после всех попыток")

    def _calculate_orders_stats(self, orders: List[Dict]) -> Tuple[int, float]:
        """Рассчитать статистику из списка заказов"""
        if not orders:
            logger.info("Нет заказов за сегодня")
            return 0, 0.0

        total_quantity = 0
        total_amount = 0.0

        for order in orders:
            quantity = order.get("quantity", 1)
            total_quantity += quantity

            if not order.get("isCancel", False):
                total_amount += float(order.get("priceWithDisc", 0)) * quantity

        logger.info(f"Рассчитано заказов: {total_quantity} шт. на {total_amount} ₽")
        return total_quantity, total_amount

    def _calculate_sales_stats(self, sales: List[Dict]) -> Tuple[int, float]:
        """Рассчитать статистику из списка продаж"""
        if not sales:
            logger.info("Нет продаж за сегодня")
            return 0, 0.0

        total_quantity = 0
        total_amount = 0.0

        for sale in sales:
            if sale.get("isRealization", True):
                quantity = sale.get("quantity", 1)
                total_quantity += quantity
                total_amount += float(sale.get("priceWithDisc", 0)) * quantity

        logger.info(f"Рассчитано продаж: {total_quantity} шт. на {total_amount} ₽")
        return total_quantity, total_amount

    async def get_today_stats_for_message(self) -> Dict[str, any]:
        """
        Получить статистику за сегодня с задержками и повторными попытками
        """
        try:
            # Запрос заказов с повторными попытками
            orders_quantity, orders_amount = await self.get_today_orders_stats()

            # Задержка между запросами
            await asyncio.sleep(2)

            # Запрос продаж с повторными попытками
            sales_quantity, sales_amount = await self.get_today_sales_stats()

            return {
                "orders": {"quantity": orders_quantity, "amount": orders_amount},
                "sales": {"quantity": sales_quantity, "amount": sales_amount}
            }
        except Exception as e:
            logger.error(f"Ошибка при получении статистики: {e}")
            raise

    async def get_detailed_orders(self, date_from: str = None) -> List[Dict]:
        """
        Получить детальные данные заказов (неагрегированные)
        """
        if date_from is None:
            date_from = datetime.now().date().isoformat()

        params = {
            "dateFrom": date_from,
            "flag": 1
        }

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                        f"{self.base_url}/api/v1/supplier/orders",
                        headers=self.headers,
                        params=params,
                        timeout=30
                ) as response:

                    if response.status == 200:
                        return await response.json()
                    else:
                        logger.error(f"Ошибка получения детальных заказов: {response.status}")
                        return []

        except Exception as e:
            logger.error(f"Ошибка получения детальных заказов: {e}")
            return []

    async def get_detailed_sales(self, date_from: str = None) -> List[Dict]:
        """
        Получить детальные данные продаж (неагрегированные)
        """
        if date_from is None:
            date_from = datetime.now().date().isoformat()

        params = {
            "dateFrom": date_from,
            "flag": 1
        }

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                        f"{self.base_url}/api/v1/supplier/sales",
                        headers=self.headers,
                        params=params,
                        timeout=30
                ) as response:

                    if response.status == 200:
                        return await response.json()
                    else:
                        logger.error(f"Ошибка получения детальных продаж: {response.status}")
                        return []

        except Exception as e:
            logger.error(f"Ошибка получения детальных продаж: {e}")
            return []

    def _get_yesterday_date_range(self) -> Tuple[str, str]:
        """
        Получить даты для вчерашних суток в формате RFC3339 с часовым поясом
        """
        from datetime import datetime, timedelta, timezone
        import pytz

        moscow_tz = pytz.timezone('Europe/Moscow')
        now = datetime.now(moscow_tz)
        yesterday = now - timedelta(days=1)

        # Начало вчерашнего дня (00:00)
        date_from = yesterday.replace(hour=0, minute=0, second=0, microsecond=0)
        # Конец вчерашнего дня (23:59:59)
        date_to = yesterday.replace(hour=23, minute=59, second=59, microsecond=0)

        # Форматируем в RFC3339
        date_from_str = date_from.isoformat()
        date_to_str = date_to.isoformat()

        return date_from_str, date_to_str

    async def get_yesterday_orders_detailed(self) -> List[Dict]:
        """
        Получить детальные данные заказов за вчерашний день
        Используем ТОЛЬКО API заказов (/api/v1/supplier/orders)
        """
        from datetime import datetime, timedelta

        yesterday = datetime.now().date() - timedelta(days=1)
        date_from = yesterday.strftime("%Y-%m-%d")

        params = {
            "dateFrom": date_from,
            "flag": 1
        }

        logger.info(f"📦 Запрос заказов за вчера ({date_from}) с flag=1")
        logger.info(f"🔗 Эндпоинт: /api/v1/supplier/orders")

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                        f"{self.base_url}/api/v1/supplier/orders",
                        headers=self.headers,
                        params=params,
                        timeout=30
                ) as response:
                    if response.status == 200:
                        orders = await response.json()
                        logger.info(f"✅ Получено заказов за вчера: {len(orders)}")

                        # Анализ данных для отладки
                        if orders:
                            cancelled = sum(1 for o in orders if o.get('isCancel', False))
                            realization_true = sum(
                                1 for o in orders if o.get('isRealization', True) and not o.get('isCancel', False))
                            realization_false = sum(
                                1 for o in orders if not o.get('isRealization', True) and not o.get('isCancel', False))

                            logger.info(f"📊 Анализ полученных данных:")
                            logger.info(f"   Отменено: {cancelled}")
                            logger.info(f"   Выкуплено: {realization_true}")
                            logger.info(f"   Не выкуплено: {realization_false}")

                            # Пример записи
                            sample = orders[0]
                            logger.info(f"📝 Пример: supplierArticle={sample.get('supplierArticle')}, "
                                        f"isCancel={sample.get('isCancel')}, "
                                        f"isRealization={sample.get('isRealization')}")

                        return orders
                    else:
                        error_text = await response.text() if response.status != 200 else ""
                        logger.error(f"❌ Ошибка получения заказов за вчера: {response.status}")
                        logger.error(f"Ошибка текст: {error_text[:200]}")

                        # Детальный анализ ошибки
                        if response.status == 401:
                            logger.error("Вероятные причины ошибки 401:")
                            logger.error("1. API ключ неверный или просрочен")
                            logger.error("2. API ключ имеет неправильный формат")
                            logger.error("3. Нет доступа к статистике")
                            logger.error(f"Использованный ключ: {self.api_key[:50]}...")

                        return []
        except asyncio.TimeoutError:
            logger.error("⏰ Таймаут при запросе заказов за вчера")
            return []
        except Exception as e:
            logger.error(f"❌ Неожиданная ошибка при запросе заказов: {e}")
            return []

    async def get_yesterday_sales_detailed(self) -> List[Dict]:
        """
        Получить детальные данные продаж за вчерашний день
        """
        from datetime import datetime, timedelta

        # Получаем дату вчера
        yesterday = datetime.now().date() - timedelta(days=1)

        # Правильный формат для WB API: YYYY-MM-DD (без времени)
        date_from = yesterday.strftime("%Y-%m-%d")

        params = {
            "dateFrom": date_from,
            "flag": 1  # Ключевой параметр! flag=1 означает "за конкретную дату"
        }

        logger.info(f"Запрос продаж за вчера ({date_from}) с flag=1")

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                        f"{self.base_url}/api/v1/supplier/sales",
                        headers=self.headers,
                        params=params,
                        timeout=30
                ) as response:
                    if response.status == 200:
                        sales = await response.json()
                        logger.info(f"Получено продаж за вчера: {len(sales)}")

                        # Отладочный вывод первых записей
                        if sales:
                            logger.info(f"Пример данных: Дата продажи: {sales[0].get('date')}, "
                                        f"Артикул: {sales[0].get('supplierArticle')}, "
                                        f"Последнее изменение: {sales[0].get('lastChangeDate')}")

                        return sales
                    else:
                        error_text = await response.text() if response.status != 200 else ""
                        logger.error(f"Ошибка получения продаж за вчера: {response.status} - {error_text[:200]}")
                        return []
        except Exception as e:
            logger.error(f"Ошибка получения продаж за вчера: {e}")
            return []
