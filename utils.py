import os
import requests
import json
import time
from datetime import datetime, timedelta
from dotenv import load_dotenv

# Загружаем переменные из .env файла
load_dotenv()

# Ваш API токен из личного кабинета Wildberries
API_TOKEN = os.getenv('API_TOKEN')

# Базовые URL для API
STATISTICS_URL = os.getenv('STATISTICS_URL', 'https://statistics-api.wildberries.ru')

# Заголовки для авторизации
headers = {
    'Authorization': f'Bearer {API_TOKEN}',
    'Content-Type': 'application/json'
}

# Глобальная переменная для отслеживания последнего запроса
last_request_time = 0


def make_request_with_delay(url, params=None, delay=1.0):
    """
    Выполняет запрос с задержкой для соблюдения лимитов API
    """
    global last_request_time

    # Вычисляем время ожидания
    current_time = time.time()
    time_since_last_request = current_time - last_request_time
    if time_since_last_request < delay:
        sleep_time = delay - time_since_last_request
        print(f"Ожидание {sleep_time:.2f} сек для соблюдения лимитов API...")
        time.sleep(sleep_time)

    # Выполняем запрос
    response = requests.get(url, headers=headers, params=params)
    last_request_time = time.time()

    return response


def get_orders(date_from=None):
    """
    Получение заказов из Statistics API.
    Использует endpoint /api/v1/supplier/orders
    """
    if date_from is None:
        date_from = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')

    url = f'{STATISTICS_URL}/api/v1/supplier/orders'
    params = {
        'dateFrom': date_from,
        'flag': 0
    }

    response = make_request_with_delay(url, params, delay=0.5)

    if response.status_code == 200:
        orders = response.json()
        print(f'Получено {len(orders)} заказов с {date_from}.')
        return orders
    elif response.status_code == 429:
        retry_after = response.headers.get('X-Ratelimit-Retry', 5)
        print(f'Превышен лимит запросов. Повтор через {retry_after} сек...')
        time.sleep(int(retry_after))
        return get_orders(date_from)  # Рекурсивный повтор
    else:
        print(f'Ошибка при получении заказов: {response.status_code} - {response.text}')
        return None


def get_sales(date_from=None):
    """
    Получение продаж (sales) из Statistics API.
    Использует endpoint /api/v1/supplier/sales
    """
    if date_from is None:
        date_from = (datetime.now() - timedelta(days=90)).strftime('%Y-%m-%d')

    url = f'{STATISTICS_URL}/api/v1/supplier/sales'
    params = {
        'dateFrom': date_from
    }

    response = make_request_with_delay(url, params, delay=0.5)

    if response.status_code == 200:
        sales = response.json()
        print(f'Получено {len(sales)} записей о продажах и возвратах.')
        return sales
    elif response.status_code == 429:
        retry_after = response.headers.get('X-Ratelimit-Retry', 5)
        print(f'Превышен лимит запросов. Повтор через {retry_after} сек...')
        time.sleep(int(retry_after))
        return get_sales(date_from)  # Рекурсивный повтор
    else:
        print(f'Ошибка при получении продаж: {response.status_code} - {response.text}')
        return None


def get_incomes(date_from=None):
    """
    Получение информации о поставках (приходах)
    Использует endpoint /api/v1/supplier/incomes
    """
    if date_from is None:
        date_from = (datetime.now() - timedelta(days=90)).strftime('%Y-%m-%d')

    url = f'{STATISTICS_URL}/api/v1/supplier/incomes'
    params = {
        'dateFrom': date_from
    }

    response = make_request_with_delay(url, params, delay=0.5)

    if response.status_code == 200:
        incomes = response.json()
        print(f'Получено {len(incomes)} записей о поставках.')
        return incomes
    else:
        print(f'Ошибка при получении поставок: {response.status_code} - {response.text}')
        return None


def calculate_dashboard_data():
    """
    Расчет данных для дашборда на основе полученной статистики
    """
    print("\n=== СБОР ДАННЫХ ===")

    # Получаем данные за разные периоды
    today = datetime.now().strftime('%Y-%m-%d')
    yesterday = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
    week_ago = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')

    # Получаем ВСЕ заказы за неделю (один запрос вместо двух)
    print("Получение данных о заказах...")
    week_orders = get_orders(week_ago) or []

    # Фильтруем за сегодня из общего списка
    today_orders = [order for order in week_orders
                    if order.get('date') and order['date'].startswith(today)]

    # Получаем ВСЕ продажи за неделю (один запрос вместо двух)
    print("Получение данных о продажах...")
    week_sales = get_sales(week_ago) or []

    # Фильтруем продажи за сегодня из общего списка
    today_sales = [sale for sale in week_sales
                   if sale.get('date') and sale['date'].startswith(today)]

    # Получаем поставки
    incomes = get_incomes(week_ago) or []

    # Анализируем данные
    def calculate_orders_stats(orders_list):
        """Расчет статистики по заказам"""
        total_count = len(orders_list)
        total_amount = sum(order.get('totalPrice', 0) for order in orders_list)
        return total_count, total_amount

    def calculate_sales_stats(sales_list):
        """Расчет статистики по продажам"""
        # Фильтруем только завершенные продажи (isRealization = True)
        completed_sales = [sale for sale in sales_list if sale.get('isRealization', False)]
        total_count = len(completed_sales)
        total_amount = sum(sale.get('finishedPrice', 0) for sale in completed_sales)
        return total_count, total_amount

    # Расчет показателей
    orders_today_count, orders_today_amount = calculate_orders_stats(today_orders)
    orders_week_count, orders_week_amount = calculate_orders_stats(week_orders)

    sales_today_count, sales_today_amount = calculate_sales_stats(today_sales)
    sales_week_count, sales_week_amount = calculate_sales_stats(week_sales)

    dashboard_data = {
        "orders": {
            "total": orders_week_count,
            "today": orders_today_count,
            "last_week": orders_week_count - orders_today_count,
            "amount": {
                "total": round(orders_week_amount, 2),
                "today": round(orders_today_amount, 2),
                "last_week": round(orders_week_amount - orders_today_amount, 2)
            }
        },
        "sales": {
            "total": sales_week_count,
            "today": sales_today_count,
            "last_week": sales_week_count - sales_today_count,
            "amount": {
                "total": round(sales_week_amount, 2),
                "today": round(sales_today_amount, 2),
                "last_week": round(sales_week_amount - sales_today_amount, 2)
            }
        },
        "incomes": {
            "count": len(incomes),
            "periods": {
                "today": today,
                "yesterday": yesterday,
                "week_ago": week_ago
            }
        },
        "last_update": datetime.now().isoformat()
    }

    return dashboard_data


def ping_api():
    """
    Проверка подключения к WB API
    """
    url = "https://common-api.wildberries.ru/ping"
    response = requests.get(url, headers=headers)

    if response.status_code == 200:
        print("Подключение к WB API успешно")
        return True
    else:
        print(f"Ошибка подключения: {response.status_code}")
        return False


def get_seller_info():
    """
    Получение информации о продавце
    """
    url = "https://common-api.wildberries.ru/api/v1/seller-info"
    response = requests.get(url, headers=headers)

    if response.status_code == 200:
        seller_info = response.json()
        print(f"Информация о продавце: {seller_info}")
        return seller_info
    else:
        print(f"Ошибка при получении информации о продавце: {response.status_code}")
        return None


def check_token_permissions():
    """
    Проверка прав токена
    """
    print("\n=== ПРОВЕРКА ПРАВ ТОКЕНА ===")

    endpoints = {
        "Статистика (заказы)": f"{STATISTICS_URL}/api/v1/supplier/orders",
        "Статистика (продажи)": f"{STATISTICS_URL}/api/v1/supplier/sales",
        "Статистика (поставки)": f"{STATISTICS_URL}/api/v1/supplier/incomes",
    }

    for name, url in endpoints.items():
        params = {'dateFrom': (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')}
        response = make_request_with_delay(url, params, delay=1.0)
        status = "✓ Доступен" if response.status_code == 200 else f"✗ Ошибка {response.status_code}"
        print(f"{name}: {status}")


# Пример использования
if __name__ == '__main__':
    print("=== ЗАПУСК СБОРЩИКА ДАННЫХ WB ===")

    # Проверяем подключение
    if ping_api():
        # Получаем информацию о продавце
        seller_info = get_seller_info()

        # Проверяем права токена
        check_token_permissions()

        # Получаем данные для дашборда
        dashboard_data = calculate_dashboard_data()

        # Сохраняем в JSON файл
        with open('wildberries_dashboard.json', 'w', encoding='utf-8') as f:
            json.dump(dashboard_data, f, indent=4, ensure_ascii=False)

        print("\n=== РЕЗУЛЬТАТЫ ===")
        print("Данные сохранены в wildberries_dashboard.json")
        print("Структура данных:")
        print(json.dumps(dashboard_data, indent=4, ensure_ascii=False))
