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

    async def get_today_orders_stats(self) -> Tuple[int, Dict[str, float], Dict[str, int]]:
        """
        Получить статистику заказов за сегодня
        Возвращает: (количество_заказов, {название_поля: сумма}, {название_поля: количество_единиц})
        """
        try:
            today = datetime.now().date()
            date_from = today.isoformat()

            params = {
                "dateFrom": date_from,
                "flag": 1
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

    async def get_today_sales_stats(self) -> Tuple[int, Dict[str, float], Dict[str, int]]:
        """
        Получить статистику продаж (выкупов) за сегодня
        Возвращает: (количество_продаж, {название_поля: сумма}, {название_поля: количество_единиц})
        """
        try:
            today = datetime.now().date()
            date_from = today.isoformat()

            params = {
                "dateFrom": date_from,
                "flag": 1
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

    def _calculate_orders_stats(self, orders: List[Dict]) -> Tuple[int, Dict[str, float], Dict[str, int]]:
        """
        Рассчитать статистику из списка заказов по всем финансовым полям и количеству единиц
        """
        if not orders:
            return 0, {
                "priceWithDisc": 0.0,
                "finishedPrice": 0.0,
                "totalPrice": 0.0
            }, {
                "total_units": 0,
                "active_units": 0,
                "cancelled_units": 0,
                "unique_articles": 0,
                "unique_nmId": 0,
                "unique_barcodes": 0
            }

        total_orders = 0
        amounts = {
            "priceWithDisc": 0.0,
            "finishedPrice": 0.0,
            "totalPrice": 0.0
        }

        # Счетчики количества единиц товара
        quantities = {
            "total_units": 0,  # Всего единиц товара в заказах
            "active_units": 0,  # Активные (не отмененные) единицы
            "cancelled_units": 0,  # Отмененные единицы
            "unique_articles": 0,  # Уникальные артикулы продавца
            "unique_nmId": 0,  # Уникальные nmId
            "unique_barcodes": 0  # Уникальные штрихкоды
        }

        # Множества для подсчета уникальных значений
        unique_articles = set()
        unique_nmId = set()
        unique_barcodes = set()

        for order in orders:
            # Считаем все единицы товара
            quantities["total_units"] += 1

            # Заполняем уникальные значения
            if supplier_article := order.get("supplierArticle"):
                unique_articles.add(supplier_article)
            if nm_id := order.get("nmId"):
                unique_nmId.add(nm_id)
            if barcode := order.get("barcode"):
                unique_barcodes.add(barcode)

            # Обрабатываем статус заказа
            if order.get("isCancel", False):
                quantities["cancelled_units"] += 1
                continue  # Пропускаем отмененные заказы для финансовых расчетов

            # Активные заказы
            total_orders += 1
            quantities["active_units"] += 1

            # Суммируем все финансовые поля
            amounts["priceWithDisc"] += float(order.get("priceWithDisc", 0))
            amounts["finishedPrice"] += float(order.get("finishedPrice", 0))
            amounts["totalPrice"] += float(order.get("totalPrice", 0))

        # Заполняем счетчики уникальных значений
        quantities["unique_articles"] = len(unique_articles)
        quantities["unique_nmId"] = len(unique_nmId)
        quantities["unique_barcodes"] = len(unique_barcodes)

        return total_orders, amounts, quantities

    def _calculate_sales_stats(self, sales: List[Dict]) -> Tuple[int, Dict[str, float], Dict[str, int]]:
        """
        Рассчитать статистику из списка продаж по всем финансовым полям и количеству единиц
        """
        if not sales:
            return 0, {
                "priceWithDisc": 0.0,
                "finishedPrice": 0.0,
                "forPay": 0.0
            }, {
                "total_units": 0,
                "sales_units": 0,
                "return_units": 0,
                "unique_articles": 0,
                "unique_nmId": 0,
                "unique_barcodes": 0,
                "unique_saleID": 0
            }

        total_sales = 0
        amounts = {
            "priceWithDisc": 0.0,
            "finishedPrice": 0.0,
            "forPay": 0.0
        }

        # Счетчики количества единиц товара
        quantities = {
            "total_units": 0,  # Всего единиц товара
            "sales_units": 0,  # Выкупленные единицы
            "return_units": 0,  # Возвращенные единицы
            "unique_articles": 0,  # Уникальные артикулы продавца
            "unique_nmId": 0,  # Уникальные nmId
            "unique_barcodes": 0,  # Уникальные штрихкоды
            "unique_saleID": 0  # Уникальные идентификаторы продаж
        }

        # Множества для подсчета уникальных значений
        unique_articles = set()
        unique_nmId = set()
        unique_barcodes = set()
        unique_saleID = set()

        for sale in sales:
            # Считаем все единицы товара
            quantities["total_units"] += 1

            # Заполняем уникальные значения
            if supplier_article := sale.get("supplierArticle"):
                unique_articles.add(supplier_article)
            if nm_id := sale.get("nmId"):
                unique_nmId.add(nm_id)
            if barcode := sale.get("barcode"):
                unique_barcodes.add(barcode)
            if sale_id := sale.get("saleID"):
                unique_saleID.add(sale_id)

            # Обрабатываем статус продажи
            if sale.get("isRealization", True):
                # Выкупленные товары
                total_sales += 1
                quantities["sales_units"] += 1

                # Суммируем все финансовые поля
                amounts["priceWithDisc"] += float(sale.get("priceWithDisc", 0))
                amounts["finishedPrice"] += float(sale.get("finishedPrice", 0))
                amounts["forPay"] += float(sale.get("forPay", 0))
            else:
                # Возвраты
                quantities["return_units"] += 1

        # Заполняем счетчики уникальных значений
        quantities["unique_articles"] = len(unique_articles)
        quantities["unique_nmId"] = len(unique_nmId)
        quantities["unique_barcodes"] = len(unique_barcodes)
        quantities["unique_saleID"] = len(unique_saleID)

        return total_sales, amounts, quantities

    async def get_today_full_stats(self) -> Dict[str, any]:
        """
        Получить полную статистику за сегодня (заказы + продажи)
        """
        try:
            orders_count, orders_amounts, orders_quantities = await self.get_today_orders_stats()
            sales_count, sales_amounts, sales_quantities = await self.get_today_sales_stats()

            return {
                "orders": {
                    "count": orders_count,
                    "amounts": orders_amounts,
                    "quantities": orders_quantities
                },
                "sales": {
                    "count": sales_count,
                    "amounts": sales_amounts,
                    "quantities": sales_quantities
                }
            }

        except Exception as e:
            logger.error(f"Ошибка при получении полной статистики: {e}")
            raise
