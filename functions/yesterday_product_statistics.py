# functions/yesterday_product_statistics.py
import aiohttp
import asyncio
from datetime import datetime, timedelta
from typing import List, Dict, Tuple, Optional
import logging
from functools import wraps

logger = logging.getLogger(__name__)


class YesterdayProductStatistics:
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://seller-analytics-api.wildberries.ru"
        self.headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "accept": "application/json"
        }

    def _retry_decorator(max_retries: int = 5, initial_delay: int = 30):
        """Декоратор для повторных попыток"""

        def decorator(func):
            @wraps(func)
            async def wrapper(self, *args, **kwargs):
                last_error = None

                for attempt in range(max_retries):
                    try:
                        return await func(self, *args, **kwargs)

                    except asyncio.TimeoutError:
                        logger.warning(f"Таймаут запроса {func.__name__} (попытка {attempt + 1}/{max_retries})")
                        last_error = "Таймаут запроса"
                        if attempt < max_retries - 1:
                            wait_time = initial_delay * (attempt + 1)
                            logger.info(f"Ждем {wait_time} секунд перед повторной попыткой")
                            await asyncio.sleep(wait_time)
                            continue
                        else:
                            raise ValueError("Таймаут запроса")

                    except aiohttp.ClientResponseError as e:
                        if e.status == 401:
                            logger.error("Ошибка 401: Неверный API ключ")
                            raise ValueError("Неверный API ключ")
                        elif e.status == 429:
                            logger.warning(f"Превышен лимит запросов (попытка {attempt + 1})")
                            last_error = "Превышен лимит запросов"
                            wait_time = initial_delay * (attempt + 1)
                            logger.info(f"Ждем {wait_time} секунд перед повторной попыткой")
                            await asyncio.sleep(wait_time)
                            continue
                        else:
                            logger.error(f"Ошибка API: {e.status}")
                            last_error = f"Ошибка сервера: {e.status}"
                            if attempt < max_retries - 1:
                                await asyncio.sleep(30)
                                continue
                            else:
                                raise ValueError(f"Ошибка сервера: {e.status}")

                    except Exception as e:
                        error_msg = str(e)
                        if "Неверный API ключ" in error_msg:
                            raise
                        logger.warning(
                            f"Неожиданная ошибка при выполнении {func.__name__} (попытка {attempt + 1}): {e}")
                        last_error = "Ошибка подключения"
                        if attempt < max_retries - 1:
                            await asyncio.sleep(30)
                            continue
                        else:
                            raise ValueError("Ошибка подключения")

                # Если дошли досюда - все попытки исчерпаны
                raise ValueError(last_error or "Не удалось получить данные после всех попыток")

            return wrapper

        return decorator

    def _get_yesterday_date(self) -> tuple:
        """Получить дату вчерашнего дня"""
        yesterday = datetime.now() - timedelta(days=1)
        date_str_dd_mm_yyyy = yesterday.strftime("%d.%m.%Y")
        date_str_yyyy_mm_dd = yesterday.strftime("%Y-%m-%d")
        return date_str_dd_mm_yyyy, date_str_yyyy_mm_dd, yesterday

    def _prepare_payload(self, target_date: datetime, limit: int = 1000, offset: int = 0) -> Dict:
        """Подготовить payload для запроса API воронки продаж"""
        # Период сравнения - неделя назад
        past_start = (target_date - timedelta(days=7)).strftime("%Y-%m-%d")
        past_end = (target_date - timedelta(days=1)).strftime("%Y-%m-%d")

        selected_start = target_date.strftime("%Y-%m-%d")
        selected_end = target_date.strftime("%Y-%m-%d")

        payload = {
            "selectedPeriod": {
                "start": selected_start,
                "end": selected_end
            },
            "pastPeriod": {
                "start": past_start,
                "end": past_end
            },
            "nmIds": [],  # Все товары
            "brandNames": [],  # Все бренды
            "subjectIds": [],  # Все категории
            "tagIds": [],  # Все теги
            "skipDeletedNm": False,
            "orderBy": {
                "field": "openCard",  # Сортировка по просмотрам
                "mode": "desc"
            },
            "limit": min(limit, 1000),
            "offset": offset
        }

        return payload

    @_retry_decorator(max_retries=3, initial_delay=20)
    async def _make_request(self, payload: Dict) -> Optional[Dict]:
        """Выполнить запрос к API воронки продаж"""
        url = f"{self.base_url}/api/analytics/v3/sales-funnel/products"

        async with aiohttp.ClientSession() as session:
            async with session.post(
                    url,
                    headers=self.headers,
                    json=payload,
                    timeout=60
            ) as response:

                if response.status == 200:
                    data = await response.json()
                    return data
                elif response.status == 401:
                    raise aiohttp.ClientResponseError(
                        request_info=None,
                        history=None,
                        status=401,
                        message="Неверный API ключ"
                    )
                elif response.status == 429:
                    raise aiohttp.ClientResponseError(
                        request_info=None,
                        history=None,
                        status=429,
                        message="Превышен лимит запросов"
                    )
                else:
                    raise aiohttp.ClientResponseError(
                        request_info=None,
                        history=None,
                        status=response.status,
                        message=f"Ошибка сервера: {response.status}"
                    )

    async def get_yesterday_sales_funnel_data(self, batch_size: int = 500) -> List[Dict]:
        """
        Получить ВСЕ данные по воронке продаж за вчера с пагинацией
        """
        date_str_dd_mm_yyyy, date_str_yyyy_mm_dd, yesterday_date = self._get_yesterday_date()

        all_products = []
        offset = 0
        page = 1

        logger.info(f"Начало извлечения данных по товарам за {date_str_dd_mm_yyyy}")

        while True:
            logger.info(f"Запрос страницы {page}, offset: {offset}")

            # Подготовка payload
            payload = self._prepare_payload(yesterday_date, limit=batch_size, offset=offset)

            # Выполнение запроса
            data = await self._make_request(payload)

            if not data:
                logger.warning(f"Не удалось получить данные для страницы {page}")
                break

            # Извлечение продуктов из ответа
            products = []
            if "data" in data and "products" in data["data"]:
                products = data["data"]["products"]
            elif "products" in data:
                products = data["products"]
            else:
                logger.warning(f"Неожиданная структура ответа: {list(data.keys())}")
                break

            if not products:
                logger.info("Больше нет данных (пустой массив продуктов)")
                break

            # Добавление продуктов в общий список
            all_products.extend(products)
            logger.info(f"Страница {page}: получено {len(products)} записей, всего {len(all_products)}")

            # Проверка на последнюю страницу
            if len(products) < batch_size:
                logger.info(f"Это последняя страница. Всего записей: {len(all_products)}")
                break

            # Пагинация
            offset += batch_size
            page += 1

            # Задержка для соблюдения лимитов API
            await asyncio.sleep(20)

        logger.info(f"Извлечение завершено. Всего получено записей за вчера: {len(all_products)}")
        return all_products, date_str_dd_mm_yyyy, date_str_yyyy_mm_dd

    async def get_yesterday_product_stats(self) -> Dict[str, any]:
        """
        Получить агрегированную статистику по товарам за вчера
        С добавлением buyoutCount и buyoutSum
        """
        try:
            # Получаем данные
            all_data, date_str_dd_mm_yyyy, date_str_yyyy_mm_dd = await self.get_yesterday_sales_funnel_data()

            if not all_data:
                logger.info("Нет данных по товарам за вчера")
                return {
                    "date": date_str_dd_mm_yyyy,
                    "total_products": 0,
                    "total_views": 0,
                    "total_carts": 0,
                    "total_orders": 0,
                    "total_order_sum": 0.0,
                    "total_buyouts": 0,           # Добавлено
                    "total_buyout_sum": 0.0,      # Добавлено
                    "active_products": 0,
                    "products_with_sales": 0,
                    "products_with_buyouts": 0,   # Добавлено
                    "products": [],
                    "all_products": []
                }

            # Рассчитываем статистику
            product_stats = {}
            total_views = 0
            total_carts = 0
            total_orders = 0
            total_order_sum = 0.0
            total_buyouts = 0           # Добавлено
            total_buyout_sum = 0.0      # Добавлено
            active_products = 0
            products_with_sales = 0
            products_with_buyouts = 0   # Добавлено

            for item in all_data:
                product = item.get("product", {})
                statistic = item.get("statistic", {}).get("selected", {})

                nm_id = product.get("nmId")
                vendor_code = product.get("vendorCode", "")
                title = product.get("title", "")
                brand = product.get("brandName", "")
                category = product.get("subjectName", "")

                # Статистика
                views = statistic.get("openCount", 0)
                carts = statistic.get("cartCount", 0)
                orders = statistic.get("orderCount", 0)
                order_sum = statistic.get("orderSum", 0)
                buyouts = statistic.get("buyoutCount", 0)      # Добавлено
                buyout_sum = statistic.get("buyoutSum", 0)     # Добавлено

                # Проверяем активность
                has_activity = views > 0 or carts > 0 or orders > 0 or buyouts > 0
                has_sales = orders > 0
                has_buyouts = buyouts > 0                      # Добавлено

                if has_activity:
                    active_products += 1
                if has_sales:
                    products_with_sales += 1
                if has_buyouts:                                # Добавлено
                    products_with_buyouts += 1

                # Используем vendorCode или nmId как ключ
                article = vendor_code if vendor_code else str(nm_id)

                if article not in product_stats:
                    product_stats[article] = {
                        'nm_id': nm_id,
                        'vendor_code': vendor_code,
                        'title': title[:100] if title else "",
                        'brand': brand,
                        'category': category,
                        'views': 0,
                        'carts': 0,
                        'orders': 0,
                        'order_sum': 0.0,
                        'buyouts': 0,           # Добавлено
                        'buyout_sum': 0.0,      # Добавлено
                        'conversion_to_cart': 0.0,
                        'conversion_to_order': 0.0,
                        'buyout_percent': 0.0   # Добавлено: процент выкупа
                    }

                # Обновляем статистику
                product_stats[article]['views'] += views
                product_stats[article]['carts'] += carts
                product_stats[article]['orders'] += orders
                product_stats[article]['order_sum'] += order_sum
                product_stats[article]['buyouts'] += buyouts        # Добавлено
                product_stats[article]['buyout_sum'] += buyout_sum  # Добавлено

                # Рассчитываем конверсии
                if views > 0:
                    product_stats[article]['conversion_to_cart'] = (carts / views) * 100
                if carts > 0:
                    product_stats[article]['conversion_to_order'] = (orders / carts) * 100
                # Рассчитываем процент выкупа
                if orders > 0:
                    product_stats[article]['buyout_percent'] = (buyouts / orders) * 100

                # Общая статистика
                total_views += views
                total_carts += carts
                total_orders += orders
                total_order_sum += order_sum
                total_buyouts += buyouts          # Добавлено
                total_buyout_sum += buyout_sum    # Добавлено

            # Сортируем товары по сумме выкупов (теперь у нас есть этот показатель)
            sorted_products = sorted(
                product_stats.items(),
                key=lambda x: x[1]['buyout_sum'],  # Сортировка по сумме выкупов
                reverse=True
            )

            # Форматируем продукты для вывода
            formatted_products = []
            for article, stats in sorted_products:
                # Пропускаем товары без продаж (если нужно)
                if stats['buyout_sum'] == 0 and stats['order_sum'] == 0:
                    continue

                formatted_products.append({
                    'article': article,
                    'nm_id': stats['nm_id'],
                    'title': stats['title'],
                    'brand': stats['brand'],
                    'category': stats['category'],
                    'views': stats['views'],
                    'carts': stats['carts'],
                    'orders': stats['orders'],
                    'order_sum': stats['order_sum'],
                    'buyouts': stats['buyouts'],          # Добавлено
                    'buyout_sum': stats['buyout_sum'],    # Добавлено
                    'buyout_percent': stats['buyout_percent'],  # Добавлено
                    'conversion_to_cart': stats['conversion_to_cart'],
                    'conversion_to_order': stats['conversion_to_order']
                })

            logger.info(f"Обработано артикулов: {len(product_stats)}")
            logger.info(f"Товаров с активностью: {active_products}")
            logger.info(f"Товаров с продажами: {products_with_sales}")
            logger.info(f"Товаров с выкупами: {products_with_buyouts}")
            logger.info(f"Всего выкупов: {total_buyouts} шт. на {total_buyout_sum:.2f} руб.")

            return {
                "date": date_str_dd_mm_yyyy,
                "total_products": len(all_data),
                "total_views": total_views,
                "total_carts": total_carts,
                "total_orders": total_orders,
                "total_order_sum": total_order_sum,
                "total_buyouts": total_buyouts,          # Добавлено
                "total_buyout_sum": total_buyout_sum,    # Добавлено
                "active_products": active_products,
                "products_with_sales": products_with_sales,
                "products_with_buyouts": products_with_buyouts,  # Добавлено
                "products": formatted_products[:50],  # Топ 50 для отображения
                "all_products": formatted_products,   # Все товары для сохранения в БД
                "overall_cart_conversion": (total_carts / total_views * 100) if total_views > 0 else 0,
                "overall_order_conversion": (total_orders / total_carts * 100) if total_carts > 0 else 0,
                "overall_buyout_percent": (total_buyouts / total_orders * 100) if total_orders > 0 else 0  # Добавлено
            }

        except Exception as e:
            logger.error(f"Ошибка при получении статистики по товарам: {e}")
            raise
