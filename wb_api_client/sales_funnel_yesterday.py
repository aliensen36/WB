# sales_funnel_yesterday.py
import json
import requests
import time
import logging
import sys
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from config import Config

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('sales_funnel_yesterday.log', encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)


class YesterdaySalesFunnelExtractor:
    def __init__(self):
        """Инициализация с загрузкой конфигурации"""
        self.config = Config()
        self.api_token = self.config.API_TOKEN

        if not self.api_token:
            logger.error("API_TOKEN не найден в конфигурации")
            sys.exit(1)

        # Базовый URL из сваггера
        self.base_url = "https://seller-analytics-api.wildberries.ru"
        self.headers = {
            "Authorization": f"Bearer {self.api_token}",
            "Content-Type": "application/json",
            "accept": "application/json"
        }

        logger.info("Инициализирован YesterdaySalesFunnelExtractor")

    def get_yesterday_date(self) -> tuple:
        """
        Получить дату вчерашнего дня в разных форматах

        Returns:
            Кортеж: (date_str_dd_mm_yyyy, date_str_yyyy_mm_dd, date_obj)
        """
        yesterday = datetime.now() - timedelta(days=1)

        # Формат DD.MM.YYYY для вывода
        date_str_dd_mm_yyyy = yesterday.strftime("%d.%m.%Y")

        # Формат YYYY-MM-DD для API
        date_str_yyyy_mm_dd = yesterday.strftime("%Y-%m-%d")

        logger.info(f"Вчерашняя дата: {date_str_dd_mm_yyyy}")
        return date_str_dd_mm_yyyy, date_str_yyyy_mm_dd, yesterday

    def prepare_periods(self, target_date: datetime):
        """
        Подготовить периоды для запроса (вчерашний день и период сравнения)

        Args:
            target_date: Дата вчерашнего дня

        Returns:
            Кортеж (selected_start, selected_end, past_start, past_end)
        """
        # Selected period: вчерашний день
        selected_start = target_date.strftime("%Y-%m-%d")
        selected_end = target_date.strftime("%Y-%m-%d")

        # Past period: неделя назад (7 дней), как в примере из сваггера
        # Можно также использовать год назад для точного сравнения
        past_date_start = target_date - timedelta(days=7)
        past_date_end = target_date - timedelta(days=1)

        past_start = past_date_start.strftime("%Y-%m-%d")
        past_end = past_date_end.strftime("%Y-%m-%d")

        logger.debug(f"Selected период: {selected_start} - {selected_end}")
        logger.debug(f"Past период: {past_start} - {past_end}")

        return selected_start, selected_end, past_start, past_end

    def make_request(self, payload: Dict, retry_count: int = 3) -> Optional[Dict]:
        """
        Выполнить запрос к API с обработкой ошибок и повторными попытками
        """
        url = f"{self.base_url}/api/analytics/v3/sales-funnel/products"

        for attempt in range(retry_count):
            try:
                if attempt > 0:
                    logger.info(f"Повторный запрос (попытка {attempt + 1}/{retry_count})")

                response = requests.post(
                    url,
                    headers=self.headers,
                    json=payload,
                    timeout=60
                )

                # Обработка HTTP ошибок
                if response.status_code == 429:
                    logger.warning("Превышен лимит запросов. Ожидание 20 секунд...")
                    time.sleep(20)
                    continue

                elif response.status_code == 401:
                    logger.error("Ошибка авторизации. Проверьте API токен")
                    return None

                elif response.status_code == 404:
                    logger.error(f"URL не найден: {url}")
                    return None

                elif response.status_code == 403:
                    logger.error("Доступ запрещен")
                    return None

                elif response.status_code == 400:
                    logger.error(f"Неправильный запрос: {response.text[:200]}")
                    return None

                elif response.status_code != 200:
                    logger.error(f"Ошибка API: {response.status_code}")
                    logger.error(f"Ответ: {response.text[:200]}")
                    time.sleep(5)
                    continue

                # Успешный ответ
                data = response.json()
                logger.info("Запрос успешен")
                return data

            except requests.exceptions.Timeout:
                logger.warning(f"Таймаут запроса (попытка {attempt + 1})")
                time.sleep(10)

            except requests.exceptions.ConnectionError:
                logger.warning(f"Ошибка соединения (попытка {attempt + 1})")
                time.sleep(10)

            except requests.exceptions.RequestException as e:
                logger.error(f"Ошибка запроса: {e}")
                time.sleep(10)

            except json.JSONDecodeError as e:
                logger.error(f"Ошибка декодирования JSON: {e}")
                logger.error(f"Ответ сервера: {response.text[:500]}")
                return None

            except Exception as e:
                logger.error(f"Неожиданная ошибка: {e}")
                time.sleep(10)

        logger.error("Все попытки запроса завершились неудачей")
        return None

    def prepare_payload(self, target_date: datetime, limit: int = 1000, offset: int = 0) -> Dict:
        """
        Подготовить payload для запроса

        Args:
            target_date: Дата вчерашнего дня
            limit: Количество записей на странице (макс 1000)
            offset: Смещение для пагинации

        Returns:
            Словарь с данными для запроса
        """
        # Подготавливаем периоды
        selected_start, selected_end, past_start, past_end = self.prepare_periods(target_date)

        # Создаем payload согласно спецификации API
        payload = {
            "selectedPeriod": {
                "start": selected_start,
                "end": selected_end
            },
            "pastPeriod": {
                "start": past_start,
                "end": past_end
            },
            "nmIds": [],  # Пустой массив = все товары
            "brandNames": [],  # Пустой массив = все бренды
            "subjectIds": [],  # Пустой массив = все категории
            "tagIds": [],  # Пустой массив = все теги
            "skipDeletedNm": False,
            "orderBy": {
                "field": "openCard",  # Сортировка по просмотрам карточек
                "mode": "desc"  # По убыванию
            },
            "limit": min(limit, 1000),  # Ограничиваем максимальный лимит
            "offset": offset
        }

        return payload

    def extract_all_data(self, batch_size: int = 500) -> List[Dict]:
        """
        Извлечь ВСЕ данные за вчерашний день с пагинацией

        Args:
            batch_size: Размер пачки данных

        Returns:
            Список всех товаров с данными за вчера
        """
        # Получаем дату вчерашнего дня
        date_str_dd_mm_yyyy, date_str_yyyy_mm_dd, yesterday_date = self.get_yesterday_date()

        all_products = []
        offset = 0
        page = 1

        logger.info(f"Начало извлечения данных за {date_str_dd_mm_yyyy} (вчера)")

        while True:
            logger.info(f"Запрос страницы {page}, offset: {offset}")

            # Подготовка payload
            payload = self.prepare_payload(yesterday_date, limit=batch_size, offset=offset)

            # Выполнение запроса
            data = self.make_request(payload)

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
                # Сохраняем сырой ответ для отладки
                with open('debug_response.json', 'w', encoding='utf-8') as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)
                break

            if not products:
                logger.info("Больше нет данных (пустой массив продуктов)")
                break

            # Добавление продуктов в общий список
            all_products.extend(products)
            logger.info(f"Страница {page}: получено {len(products)} записей, всего {len(all_products)}")

            # Проверка на последнюю страницу (если получено меньше запрошенного)
            if len(products) < batch_size:
                logger.info(f"Это последняя страница. Всего записей: {len(all_products)}")
                break

            # Пагинация
            offset += batch_size
            page += 1

            # Задержка для соблюдения лимитов API (3 запроса в минуту)
            logger.debug("Задержка 20 секунд для соблюдения лимитов API")
            time.sleep(20)

        logger.info(f"Извлечение завершено. Всего получено записей за вчера: {len(all_products)}")
        return all_products, date_str_dd_mm_yyyy, date_str_yyyy_mm_dd

    def save_to_file(self, data: List[Dict], date_str: str):
        """
        Сохранить данные в JSON файл

        Args:
            data: Данные для сохранения
            date_str: Дата для формирования имени файла
        """
        if not data:
            logger.warning("Нет данных для сохранения")
            return

        # Генерация имени файла
        clean_date = date_str.replace(".", "_")
        filename = f"sales_funnel_{clean_date}.json"

        try:
            # Сохранение данных
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)

            logger.info(f"Данные успешно сохранены в файл: {filename}")
            logger.info(f"Всего сохранено записей: {len(data)}")

            # Вывод информации о размере файла
            import os
            file_size = os.path.getsize(filename)
            logger.info(f"Размер файла: {file_size / 1024:.2f} KB ({file_size} bytes)")

            return filename

        except IOError as e:
            logger.error(f"Ошибка записи в файл {filename}: {e}")
        except Exception as e:
            logger.error(f"Неожиданная ошибка при сохранении: {e}")

        return None

    def calculate_statistics(self, data: List[Dict]) -> Dict:
        """
        Рассчитать статистику по извлеченным данным

        Args:
            data: Извлеченные данные

        Returns:
            Словарь со статистикой
        """
        if not data:
            return {}

        stats = {
            "total_products": len(data),
            "active_products": 0,
            "total_views": 0,
            "total_carts": 0,
            "total_orders": 0,
            "total_order_sum": 0,
            "total_buyouts": 0,
            "total_buyout_sum": 0,
            "top_products_by_views": [],
            "brand_distribution": {},
            "category_distribution": {}
        }

        for item in data:
            product = item.get("product", {})
            stat = item.get("statistic", {}).get("selected", {})

            # Проверяем активность
            is_active = (stat.get("openCount", 0) > 0 or
                         stat.get("cartCount", 0) > 0 or
                         stat.get("orderCount", 0) > 0)

            if is_active:
                stats["active_products"] += 1

            # Суммируем показатели
            stats["total_views"] += stat.get("openCount", 0)
            stats["total_carts"] += stat.get("cartCount", 0)
            stats["total_orders"] += stat.get("orderCount", 0)
            stats["total_order_sum"] += stat.get("orderSum", 0)
            stats["total_buyouts"] += stat.get("buyoutCount", 0)
            stats["total_buyout_sum"] += stat.get("buyoutSum", 0)

            # Распределение по брендам
            brand = product.get("brandName", "Без бренда")
            stats["brand_distribution"][brand] = stats["brand_distribution"].get(brand, 0) + 1

            # Распределение по категориям
            category = product.get("subjectName", "Без категории")
            stats["category_distribution"][category] = stats["category_distribution"].get(category, 0) + 1

        # Топ-5 товаров по просмотрам
        sorted_by_views = sorted(
            data,
            key=lambda x: x.get("statistic", {}).get("selected", {}).get("openCount", 0),
            reverse=True
        )[:5]

        for item in sorted_by_views:
            product = item.get("product", {})
            stat = item.get("statistic", {}).get("selected", {})
            stats["top_products_by_views"].append({
                "nmId": product.get("nmId"),
                "title": product.get("title", "")[:50],
                "views": stat.get("openCount", 0),
                "orders": stat.get("orderCount", 0)
            })

        return stats

    def print_summary(self, data: List[Dict], date_str: str, stats: Dict):
        """
        Вывести краткую статистику по извлеченным данным

        Args:
            data: Извлеченные данные
            date_str: Дата данных
            stats: Рассчитанная статистика
        """
        if not data:
            logger.info("Нет данных для вывода статистики")
            return

        logger.info("\n" + "=" * 60)
        logger.info("СТАТИСТИКА ДАННЫХ ЗА ВЧЕРА")
        logger.info("=" * 60)
        logger.info(f"Дата: {date_str}")
        logger.info(f"Всего товаров: {stats['total_products']}")
        logger.info(
            f"Активных товаров: {stats['active_products']} ({stats['active_products'] / stats['total_products'] * 100:.1f}%)")

        logger.info("\nОБЩИЕ ПОКАЗАТЕЛИ:")
        logger.info(f"Просмотры карточек: {stats['total_views']:,}")
        logger.info(f"Добавления в корзину: {stats['total_carts']:,}")
        logger.info(f"Заказы: {stats['total_orders']:,}")
        logger.info(f"Сумма заказов: {stats['total_order_sum']:,.2f} руб.")
        logger.info(f"Выкупы: {stats['total_buyouts']:,}")
        logger.info(f"Сумма выкупа: {stats['total_buyout_sum']:,.2f} руб.")

        if stats['total_views'] > 0:
            logger.info(f"Конверсия в корзину: {stats['total_carts'] / stats['total_views'] * 100:.2f}%")

        if stats['total_carts'] > 0:
            logger.info(f"Конверсия в заказ: {stats['total_orders'] / stats['total_carts'] * 100:.2f}%")

        # Топ-5 товаров по просмотрам
        if stats["top_products_by_views"]:
            logger.info("\nТОП-5 ТОВАРОВ ПО ПРОСМОТРАМ:")
            for i, product in enumerate(stats["top_products_by_views"], 1):
                logger.info(
                    f"{i}. Арт. {product['nmId']} - {product['views']:,} просмотров, {product['orders']:,} заказов")
                logger.info(f"   {product['title']}...")

        # Топ-5 брендов
        if stats["brand_distribution"]:
            logger.info("\nТОП-5 БРЕНДОВ:")
            sorted_brands = sorted(stats["brand_distribution"].items(), key=lambda x: x[1], reverse=True)[:5]
            for brand, count in sorted_brands:
                logger.info(f"{brand}: {count} товаров ({count / stats['total_products'] * 100:.1f}%)")

        # Топ-5 категорий
        if stats["category_distribution"]:
            logger.info("\nТОП-5 КАТЕГОРИЙ:")
            sorted_categories = sorted(stats["category_distribution"].items(), key=lambda x: x[1], reverse=True)[:5]
            for category, count in sorted_categories:
                logger.info(f"{category}: {count} товаров ({count / stats['total_products'] * 100:.1f}%)")

        logger.info("=" * 60)


def main():
    """Основная функция для извлечения данных за вчера"""
    logger.info("=" * 60)
    logger.info("ЗАПУСК ИЗВЛЕЧЕНИЯ ДАННЫХ ЗА ВЧЕРАШНИЙ ДЕНЬ")
    logger.info("=" * 60)

    try:
        # Создание экземпляра извлекателя
        extractor = YesterdaySalesFunnelExtractor()

        # Извлечение всех данных за вчера
        all_data, date_str_dd_mm_yyyy, date_str_yyyy_mm_dd = extractor.extract_all_data(batch_size=500)

        if all_data:
            # Сохранение в файл
            filename = extractor.save_to_file(all_data, date_str_dd_mm_yyyy)

            if filename:
                # Расчет статистики
                stats = extractor.calculate_statistics(all_data)

                # Вывод статистики
                extractor.print_summary(all_data, date_str_dd_mm_yyyy, stats)

                # Сохранение статистики в отдельный файл
                stats_filename = f"stats_{date_str_dd_mm_yyyy.replace('.', '_')}.json"
                with open(stats_filename, 'w', encoding='utf-8') as f:
                    json.dump(stats, f, ensure_ascii=False, indent=2)
                logger.info(f"Статистика сохранена в {stats_filename}")

                logger.info("\n" + "=" * 60)
                logger.info("ВЫПОЛНЕНИЕ ЗАВЕРШЕНО УСПЕШНО!")
                logger.info("=" * 60)
            else:
                logger.error("Не удалось сохранить данные в файл")
        else:
            logger.warning("Не удалось извлечь данные за вчерашний день")

    except KeyboardInterrupt:
        logger.info("\nВыполнение прервано пользователем")
    except Exception as e:
        logger.error(f"Критическая ошибка: {e}", exc_info=True)
        sys.exit(1)


# Упрощенная версия для быстрого запуска
def quick_extract():
    """Быстрое извлечение данных за вчера без пагинации"""
    from config import Config

    config = Config()
    api_token = config.API_TOKEN

    if not api_token:
        print("Ошибка: API_TOKEN не найден в .env файле")
        return

    # Получаем дату вчерашнего дня
    yesterday = datetime.now() - timedelta(days=1)
    date_str_dd_mm_yyyy = yesterday.strftime("%d.%m.%Y")
    date_str_yyyy_mm_dd = yesterday.strftime("%Y-%m-%d")

    print(f"Извлечение данных за {date_str_dd_mm_yyyy} (вчера)...")

    url = "https://seller-analytics-api.wildberries.ru/api/analytics/v3/sales-funnel/products"

    headers = {
        "Authorization": f"Bearer {api_token}",
        "Content-Type": "application/json",
        "accept": "application/json"
    }

    # Подготовка периодов
    past_start = (yesterday - timedelta(days=7)).strftime("%Y-%m-%d")
    past_end = (yesterday - timedelta(days=1)).strftime("%Y-%m-%d")

    payload = {
        "selectedPeriod": {
            "start": date_str_yyyy_mm_dd,
            "end": date_str_yyyy_mm_dd
        },
        "pastPeriod": {
            "start": past_start,
            "end": past_end
        },
        "nmIds": [],
        "brandNames": [],
        "subjectIds": [],
        "tagIds": [],
        "skipDeletedNm": False,
        "orderBy": {
            "field": "openCard",
            "mode": "desc"
        },
        "limit": 1000,  # Максимальное количество за один запрос
        "offset": 0
    }

    try:
        response = requests.post(url, headers=headers, json=payload, timeout=60)

        if response.status_code == 200:
            data = response.json()

            # Извлекаем продукты
            products = data.get("data", {}).get("products", [])
            print(f"Успешно! Получено товаров: {len(products)}")

            # Сохраняем в файл
            filename = f"sales_funnel_{date_str_dd_mm_yyyy.replace('.', '_')}.json"
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(products, f, ensure_ascii=False, indent=2)

            print(f"Данные сохранены в {filename}")

            # Быстрая статистика
            if products:
                total_views = sum(p.get("statistic", {}).get("selected", {}).get("openCount", 0) for p in products)
                total_orders = sum(p.get("statistic", {}).get("selected", {}).get("orderCount", 0) for p in products)
                print(f"\nСтатистика за {date_str_dd_mm_yyyy}:")
                print(f"Всего просмотров: {total_views}")
                print(f"Всего заказов: {total_orders}")

        else:
            print(f"Ошибка {response.status_code}: {response.text[:200]}")

    except Exception as e:
        print(f"Ошибка запроса: {e}")


if __name__ == "__main__":
    # Запуск основной функции
    main()
