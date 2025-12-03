# sales_funnel_01122025
import requests
import json
from datetime import datetime, timedelta
import time
from config import Config


def fetch_sales_funnel_data(api_token, start_date, end_date):
    """
    Получение данных воронки продаж за указанный период

    Args:
        api_token (str): API токен Wildberries
        start_date (str): Начало периода в формате YYYY-MM-DD
        end_date (str): Конец периода в формате YYYY-MM-DD

    Returns:
        list: Список всех товаров с данными за период
    """
    url = "https://seller-analytics-api.wildberries.ru/api/analytics/v3/sales-funnel/products"

    headers = {
        "Authorization": api_token,
        "accept": "application/json",
        "Content-Type": "application/json"
    }

    # Преобразуем даты в datetime объекты
    start_dt = datetime.strptime(start_date, "%Y-%m-%d")
    end_dt = datetime.strptime(end_date, "%Y-%m-%d")

    # Проверяем, что период не превышает 365 дней
    period_days = (end_dt - start_dt).days + 1
    if period_days > 365:
        print(f"Ошибка: Период {period_days} дней превышает максимальный лимит 365 дней")
        return []

    # Основной период
    selected_period = {
        "start": start_date,
        "end": end_date
    }

    # Для сравнения используем такой же период (1 день) за прошлый год
    # Важно: период сравнения должен быть такой же продолжительности
    past_start_date = (start_dt - timedelta(days=365)).strftime("%Y-%m-%d")
    past_end_date = (end_dt - timedelta(days=365)).strftime("%Y-%m-%d")

    past_period = {
        "start": past_start_date,
        "end": past_end_date
    }

    print(f"Основной период: {start_date} - {end_date} ({period_days} дней)")
    print(f"Период сравнения: {past_start_date} - {past_end_date} ({period_days} дней)")

    all_products = []
    limit = 1000  # Максимальное количество записей за один запрос
    offset = 0

    try:
        while True:
            # Формируем тело запроса с пагинацией
            payload = {
                "selectedPeriod": selected_period,
                "pastPeriod": past_period,
                "nmIds": [],
                "brandNames": [],
                "subjectIds": [],
                "tagIds": [],
                "skipDeletedNm": False,
                "orderBy": {
                    "field": "openCard",
                    "mode": "desc"
                },
                "limit": limit,
                "offset": offset
            }

            print(f"Запрос данных: offset={offset}, limit={limit}")

            response = requests.post(url, headers=headers, json=payload)

            # Проверка статуса ответа
            if response.status_code == 200:
                data = response.json()

                # Проверяем наличие данных
                if "data" in data and "products" in data["data"]:
                    products = data["data"]["products"]

                    if not products:
                        print("Получен пустой список товаров. Завершение пагинации.")
                        break

                    all_products.extend(products)
                    print(f"Получено {len(products)} товаров. Всего: {len(all_products)}")

                    # Если получено меньше товаров чем лимит, значит это последняя страница
                    if len(products) < limit:
                        print("Получены все данные. Завершение пагинации.")
                        break

                    # Увеличиваем offset для следующей страницы
                    offset += limit

                    # Добавляем задержку для соблюдения лимитов API
                    time.sleep(20)  # 20 секунд между запросами для соблюдения лимитов
                else:
                    print("Неожиданная структура ответа:")
                    print(json.dumps(data, indent=2, ensure_ascii=False))
                    break

            elif response.status_code == 429:
                print("Превышен лимит запросов. Ожидание 60 секунд...")
                time.sleep(60)
                continue

            elif response.status_code == 400:
                print(f"Ошибка 400 (Некорректный запрос): {response.text}")

                # Пробуем альтернативный вариант: указать только selectedPeriod
                # Некоторые API позволяют не указывать pastPeriod
                print("Пробуем отправить запрос без pastPeriod...")

                payload_without_past = {
                    "selectedPeriod": selected_period,
                    "nmIds": [],
                    "brandNames": [],
                    "subjectIds": [],
                    "tagIds": [],
                    "skipDeletedNm": False,
                    "orderBy": {
                        "field": "openCard",
                        "mode": "desc"
                    },
                    "limit": limit,
                    "offset": offset
                }

                response2 = requests.post(url, headers=headers, json=payload_without_past)

                if response2.status_code == 200:
                    data = response2.json()
                    if "data" in data and "products" in data["data"]:
                        products = data["data"]["products"]
                        if products:
                            all_products.extend(products)
                            print(f"Получено {len(products)} товаров. Всего: {len(all_products)}")

                            if len(products) < limit:
                                break
                            offset += limit
                            time.sleep(20)
                            continue

                break

            else:
                print(f"Ошибка API: {response.status_code}")
                print(f"Ответ: {response.text}")
                break

        return all_products

    except requests.exceptions.RequestException as e:
        print(f"Ошибка при выполнении запроса: {e}")
        return []
    except json.JSONDecodeError as e:
        print(f"Ошибка при разборе JSON: {e}")
        return []
    except Exception as e:
        print(f"Неожиданная ошибка: {e}")
        return []


def save_data_to_file(data, filename):
    """
    Сохранение данных в JSON файл

    Args:
        data (list): Данные для сохранения
        filename (str): Имя файла
    """
    try:
        # Если данных нет, создаем пустой файл с сообщением
        if not data:
            result = {
                "message": "Нет данных за указанный период",
                "timestamp": datetime.now().isoformat(),
                "total_items": 0,
                "items": []
            }
        else:
            result = {
                "message": "Данные успешно получены",
                "timestamp": datetime.now().isoformat(),
                "total_items": len(data),
                "items": data
            }

        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(result, f, indent=2, ensure_ascii=False)
        print(f"Данные успешно сохранены в файл: {filename}")
        print(f"Всего сохранено записей: {len(data) if data else 0}")
    except Exception as e:
        print(f"Ошибка при сохранении в файл: {e}")


def format_statistics(products):
    """
    Форматирование статистики для вывода

    Args:
        products (list): Список товаров
    """
    if not products:
        print("Нет данных для вывода статистики")
        return

    total_open = 0
    total_cart = 0
    total_order = 0
    total_order_sum = 0
    total_buyout = 0

    print("\n" + "=" * 60)
    print("СТАТИСТИКА ПО ДАННЫМ:")
    print("=" * 60)

    for i, product in enumerate(products[:10]):  # Показываем только первые 10
        prod_info = product.get('product', {})
        stat_info = product.get('statistic', {}).get('selected', {})

        print(f"\n{i + 1}. {prod_info.get('title', 'Без названия')[:60]}...")
        print(f"   Артикул: {prod_info.get('nmId', 'Н/Д')}")
        print(f"   Бренд: {prod_info.get('brandName', 'Н/Д')}")
        print(f"   Просмотры: {stat_info.get('openCount', 0):,}")
        print(f"   В корзине: {stat_info.get('cartCount', 0):,}")
        print(f"   Заказы: {stat_info.get('orderCount', 0):,}")
        print(f"   Сумма заказов: {stat_info.get('orderSum', 0):,} руб.")

        # Суммируем для общей статистики
        total_open += stat_info.get('openCount', 0)
        total_cart += stat_info.get('cartCount', 0)
        total_order += stat_info.get('orderCount', 0)
        total_order_sum += stat_info.get('orderSum', 0)
        total_buyout += stat_info.get('buyoutCount', 0)

    if len(products) > 10:
        print(f"\n... и еще {len(products) - 10} товаров")

    print("\n" + "=" * 60)
    print("ОБЩАЯ СТАТИСТИКА:")
    print("=" * 60)
    print(f"Всего товаров: {len(products):,}")
    print(f"Общее количество просмотров: {total_open:,}")
    print(f"Общее количество добавлений в корзину: {total_cart:,}")
    print(f"Общее количество заказов: {total_order:,}")
    print(f"Общая сумма заказов: {total_order_sum:,} руб.")
    print(f"Общее количество выкупов: {total_buyout:,}")

    if total_open > 0:
        print(f"\nКонверсия в корзину: {(total_cart / total_open * 100):.1f}%")
    if total_cart > 0:
        print(f"Конверсия в заказ: {(total_order / total_cart * 100):.1f}%")
    if total_order > 0:
        print(f"Средний чек: {(total_order_sum / total_order):,.0f} руб.")


def main():
    """Основная функция"""

    # Получаем API токен из конфигурации
    api_token = Config.API_TOKEN

    if not api_token:
        print("Ошибка: API_TOKEN не найден в конфигурации.")
        print("Убедитесь, что в файле .env установлена переменная API_TOKEN")
        return

    print(f"Используется API токен для аккаунта")
    print(f"Токен начинается с: {api_token[:50]}...")

    # Устанавливаем период за 01.12.2025
    start_date = "2025-12-01"
    end_date = "2025-12-01"

    print(f"\nЗапрашиваем данные за период: {start_date} - {end_date}")

    # Получаем данные через API
    all_products = fetch_sales_funnel_data(api_token, start_date, end_date)

    if all_products:
        # Генерируем имя файла с текущей датой
        current_datetime = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"sales_funnel_{start_date}_{current_datetime}.json"

        # Сохраняем данные в файл
        save_data_to_file(all_products, filename)

        # Выводим статистику
        format_statistics(all_products)

        # Дополнительная информация о файле
        print(f"\nДанные сохранены в файл: {filename}")
        print(f"Размер файла: {len(json.dumps(all_products)) / 1024:.1f} КБ")

    else:
        print("Не удалось получить данные или данные отсутствуют.")

        # Все равно создаем файл с информацией об отсутствии данных
        current_datetime = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"sales_funnel_{start_date}_{current_datetime}_EMPTY.json"
        save_data_to_file([], filename)


if __name__ == "__main__":
    main()