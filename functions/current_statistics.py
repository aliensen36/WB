# functions/current_statistics.py
import aiohttp
import asyncio
from datetime import datetime
from typing import List, Dict, Tuple
import logging

logger = logging.getLogger(__name__)


class CurrentStatistics:
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
