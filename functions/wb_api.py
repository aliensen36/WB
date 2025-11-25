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
        Возвращает: (количество_заказов, суммарная_стоимость)
        """
        try:
            # Получаем сегодняшнюю дату в формате RFC3339 (Московское время UTC+3)
            today = datetime.now().date()
            date_from = today.isoformat()  # Формат: YYYY-MM-DD

            params = {
                "dateFrom": date_from,
                "flag": 1  # Получаем все заказы за указанную дату
            }

            async with aiohttp.ClientSession() as session:
                async with session.get(
                        f"{self.base_url}/api/v1/supplier/orders",
                        headers=self.headers,
                        params=params,
                        timeout=30
                ) as response:

                    if response.status == 200:
                        orders = await response.json()
                        return self._calculate_orders_stats(orders)

                    elif response.status == 401:
                        raise ValueError("Неверный API ключ")

                    elif response.status == 429:
                        raise ValueError("Слишком много запросов. Попробуйте позже")

                    else:
                        error_text = await response.text()
                        raise ValueError(f"Ошибка API заказов: {response.status} - {error_text}")

        except asyncio.TimeoutError:
            raise ValueError("Таймаут при запросе заказов к WB API")
        except Exception as e:
            logger.error(f"Ошибка при получении статистики заказов: {e}")
            raise ValueError(f"Ошибка при получении данных заказов: {str(e)}")

    async def get_today_sales_stats(self) -> Tuple[int, float]:
        """
        Получить статистику продаж (выкупов) за сегодня
        Возвращает: (количество_продаж, суммарная_стоимость)
        """
        try:
            # Получаем сегодняшнюю дату в формате RFC3339 (Московское время UTC+3)
            today = datetime.now().date()
            date_from = today.isoformat()  # Формат: YYYY-MM-DD

            params = {
                "dateFrom": date_from,
                "flag": 1  # Получаем все продажи за указанную дату
            }

            async with aiohttp.ClientSession() as session:
                async with session.get(
                        f"{self.base_url}/api/v1/supplier/sales",
                        headers=self.headers,
                        params=params,
                        timeout=30
                ) as response:

                    if response.status == 200:
                        sales = await response.json()
                        return self._calculate_sales_stats(sales)

                    elif response.status == 401:
                        raise ValueError("Неверный API ключ")

                    elif response.status == 429:
                        raise ValueError("Слишком много запросов. Попробуйте позже")

                    else:
                        error_text = await response.text()
                        raise ValueError(f"Ошибка API продаж: {response.status} - {error_text}")

        except asyncio.TimeoutError:
            raise ValueError("Таймаут при запросе продаж к WB API")
        except Exception as e:
            logger.error(f"Ошибка при получении статистики продаж: {e}")
            raise ValueError(f"Ошибка при получении данных продаж: {str(e)}")

    def _calculate_orders_stats(self, orders: List[Dict]) -> Tuple[int, float]:
        """
        Рассчитать статистику из списка заказов
        """
        if not orders:
            return 0, 0.0

        total_orders = 0
        total_amount = 0.0

        for order in orders:
            # Пропускаем отмененные заказы
            if order.get("isCancel", False):
                continue

            price_with_disc = order.get("priceWithDisc", 0)

            # Если priceWithDisc не указан, используем finishedPrice
            if not price_with_disc:
                price_with_disc = order.get("finishedPrice", 0)

            total_orders += 1
            total_amount += float(price_with_disc)

        return total_orders, total_amount

    def _calculate_sales_stats(self, sales: List[Dict]) -> Tuple[int, float]:
        """
        Рассчитать статистику из списка продаж
        """
        if not sales:
            return 0, 0.0

        total_sales = 0
        total_amount = 0.0

        for sale in sales:
            # Продажи с isRealization=true - это выкупы
            # isRealization=false - это возвраты
            if sale.get("isRealization", True):  # По умолчанию считаем выкупами
                price_with_disc = sale.get("priceWithDisc", 0)

                # Если priceWithDisc не указан, используем finishedPrice
                if not price_with_disc:
                    price_with_disc = sale.get("finishedPrice", 0)

                total_sales += 1
                total_amount += float(price_with_disc)

        return total_sales, total_amount

    async def get_today_full_stats(self) -> Dict[str, any]:
        """
        Получить полную статистику за сегодня (заказы + продажи)
        """
        try:
            orders_count, orders_amount = await self.get_today_orders_stats()
            sales_count, sales_amount = await self.get_today_sales_stats()

            return {
                "orders": {
                    "count": orders_count,
                    "amount": orders_amount
                },
                "sales": {
                    "count": sales_count,
                    "amount": sales_amount
                }
            }

        except Exception as e:
            logger.error(f"Ошибка при получении полной статистики: {e}")
            raise
