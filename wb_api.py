import os
import requests
import json
from datetime import datetime, timedelta
from dotenv import load_dotenv

# Загружаем переменные из .env файла
load_dotenv()

# Ваш API токен из личного кабинета Wildberries
API_TOKEN = os.getenv('API_TOKEN')

# Базовые URL для API
MARKETPLACE_URL = os.getenv('MARKETPLACE_URL')
STATISTICS_URL = os.getenv('STATISTICS_URL')

# Заголовки для авторизации
headers = {
    'Authorization': f'Bearer {API_TOKEN}',
    'Content-Type': 'application/json'
}


def get_orders():
    """
    Получение новых заказов (orders) из Marketplace API.
    Использует endpoint /api/v3/orders/new
    """
    url = f'{MARKETPLACE_URL}/api/v3/orders/new'
    response = requests.get(url, headers=headers)

    if response.status_code == 200:
        orders = response.json().get('orders', [])
        print(f'Получено {len(orders)} новых заказов.')
        return orders
    else:
        print(f'Ошибка при получении заказов: {response.status_code} - {response.text}')
        return None


def get_sales(date_from=None):
    """
    Получение продаж (sales) из Statistics API.
    Использует endpoint /api/v1/supplier/sales
    date_from: дата в формате 'YYYY-MM-DD', по умолчанию - 90 дней назад
    """
    if date_from is None:
        # По умолчанию - данные за последние 90 дней (максимальный период хранения)
        date_from = (datetime.now() - timedelta(days=90)).strftime('%Y-%m-%d')

    url = f'{STATISTICS_URL}/api/v1/supplier/sales'
    params = {
        'dateFrom': date_from
    }

    response = requests.get(url, headers=headers, params=params)

    if response.status_code == 200:
        sales = response.json()
        print(f'Получено {len(sales)} записей о продажах и возвратах.')
        return sales
    else:
        print(f'Ошибка при получении продаж: {response.status_code} - {response.text}')
        return None


# Пример использования
if __name__ == '__main__':
    # Получаем заказы
    orders = get_orders()
    if orders:
        print('Пример первого заказа:')
        print(json.dumps(orders[0], indent=4, ensure_ascii=False) if orders else 'Нет заказов')

    # Получаем продажи за последние 7 дней
    recent_date = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')
    sales = get_sales(date_from=recent_date)
    if sales:
        print('Пример первой записи о продаже:')
        print(json.dumps(sales[0], indent=4, ensure_ascii=False) if sales else 'Нет продаж')