# functions/wb_api.py
import aiohttp
import asyncio
from datetime import datetime, date
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

    async def get_today_orders_stats(self) -> Tuple[int, float]:
        """
        Получить статистику заказов за сегодня
        Возвращает: (количество_заказов, сумма_по_priceWithDisc)
        """
        try:
            today = datetime.now().date()
            date_from = today.isoformat()

            params = {
                "dateFrom": date_from,
                "flag": 1
            }

            logger.info(f"Запрос заказов для даты: {date_from}")

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
                        logger.info(f"Получено заказов: {len(orders)}")
                        return self._calculate_orders_stats(orders)

                    elif response.status == 401:
                        logger.error("Ошибка 401: Неверный API ключ")
                        raise ValueError("Неверный API ключ")

                    elif response.status == 429:
                        logger.error("Ошибка 429: Слишком много запросов")
                        raise ValueError("Слишком много запросов. Попробуйте позже")

                    else:
                        error_text = await response.text()
                        logger.error(f"Ошибка API заказов: {response.status} - {error_text}")
                        raise ValueError(f"Ошибка API заказов: {response.status} - {error_text}")

        except asyncio.TimeoutError:
            logger.error("Таймаут при запросе заказов")
            raise ValueError("Таймаут при запросе заказов к WB API")
        except Exception as e:
            logger.error(f"Ошибка при получении статистики заказов: {e}")
            raise ValueError(f"Ошибка при получении данных заказов: {str(e)}")

    async def get_today_sales_stats(self) -> Tuple[int, float]:
        """
        Получить статистику продаж (выкупов) за сегодня
        Возвращает: (количество_продаж, сумма_по_priceWithDisc)
        """
        try:
            today = datetime.now().date()
            date_from = today.isoformat()

            params = {
                "dateFrom": date_from,
                "flag": 1
            }

            logger.info(f"Запрос продаж для даты: {date_from}")

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
                        logger.info(f"Получено продаж: {len(sales)}")
                        return self._calculate_sales_stats(sales)

                    elif response.status == 401:
                        logger.error("Ошибка 401: Неверный API ключ")
                        raise ValueError("Неверный API ключ")

                    elif response.status == 429:
                        logger.error("Ошибка 429: Слишком много запросов")
                        raise ValueError("Слишком много запросов. Попробуйте позже")

                    else:
                        error_text = await response.text()
                        logger.error(f"Ошибка API продаж: {response.status} - {error_text}")
                        raise ValueError(f"Ошибка API продаж: {response.status} - {error_text}")

        except asyncio.TimeoutError:
            logger.error("Таймаут при запросе продаж")
            raise ValueError("Таймаут при запросе продаж к WB API")
        except Exception as e:
            logger.error(f"Ошибка при получении статистики продаж: {e}")
            raise ValueError(f"Ошибка при получении данных продаж: {str(e)}")

    def _calculate_orders_stats(self, orders: List[Dict]) -> Tuple[int, float]:
        """
        Рассчитать статистику из списка заказов
        Считает количество заказов по quantity и сумму по priceWithDisc
        """
        if not orders:
            logger.info("Нет заказов за сегодня")
            return 0, 0.0

        total_quantity = 0
        total_amount = 0.0

        for order in orders:
            # Суммируем quantity для каждого заказа
            quantity = order.get("quantity", 1)
            total_quantity += quantity

            # Суммируем priceWithDisc для неотмененных заказов
            if not order.get("isCancel", False):
                total_amount += float(order.get("priceWithDisc", 0)) * quantity

        logger.info(f"Рассчитано заказов: quantity={total_quantity}, amount={total_amount}")
        return total_quantity, total_amount

    def _calculate_sales_stats(self, sales: List[Dict]) -> Tuple[int, float]:
        """
        Рассчитать статистику из списка продаж
        Считает количество выкупов по quantity (только isRealization=True) и сумму по priceWithDisc
        """
        if not sales:
            logger.info("Нет продаж за сегодня")
            return 0, 0.0

        total_quantity = 0
        total_amount = 0.0

        for sale in sales:
            # Считаем только выкупы (isRealization=True)
            if sale.get("isRealization", True):
                quantity = sale.get("quantity", 1)
                total_quantity += quantity
                total_amount += float(sale.get("priceWithDisc", 0)) * quantity

        logger.info(f"Рассчитано продаж: quantity={total_quantity}, amount={total_amount}")
        return total_quantity, total_amount

    async def get_today_stats_for_message(self) -> Dict[str, any]:
        """
        Получить статистику за сегодня в формате для сообщения
        """
        try:
            orders_quantity, orders_amount = await self.get_today_orders_stats()
            sales_quantity, sales_amount = await self.get_today_sales_stats()

            return {
                "orders": {
                    "quantity": orders_quantity,
                    "amount": orders_amount
                },
                "sales": {
                    "quantity": sales_quantity,
                    "amount": sales_amount
                }
            }

        except Exception as e:
            logger.error(f"Ошибка при получении статистики: {e}")
            raise
