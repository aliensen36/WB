import os
import time
import json
import requests
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()

API_TOKEN = os.getenv('API_TOKEN')
STAT_URL = os.getenv('STATISTICS_URL', 'https://statistics-api.wildberries.ru')

headers = {
    "Authorization": f"Bearer {API_TOKEN}",
    "Content-Type": "application/json"
}

last_request = 0


def make_api_request(url, params=None, delay=60.0):
    """
    Выполняет запрос к API с соблюдением лимитов (1 запрос в минуту)
    """
    global last_request

    current_time = time.time()
    time_since_last = current_time - last_request

    if time_since_last < delay:
        sleep_time = delay - time_since_last
        print(f"⏳ Ожидание {sleep_time:.1f} сек для соблюдения лимитов API...")
        time.sleep(sleep_time)

    print(f"📡 Запрос к {url.split('/')[-1]} с параметрами: {params}")
    response = requests.get(url, headers=headers, params=params)
    last_request = time.time()

    if response.status_code == 429:
        retry_after = int(response.headers.get('Retry-After', 60))
        print(f"⚠️ Лимит запросов. Ожидание {retry_after} сек...")
        time.sleep(retry_after)
        return make_api_request(url, params, delay)

    return response


def get_all_orders(date_from, max_requests=10):
    """
    Получение всех заказов с пагинацией согласно документации
    """
    all_orders = []
    current_date_from = date_from

    for request_num in range(max_requests):
        print(f"📦 Запрос заказов #{request_num + 1} с dateFrom: {current_date_from}")

        url = f"{STAT_URL}/api/v1/supplier/orders"
        params = {
            'dateFrom': current_date_from,
            'flag': 0  # Данные с lastChangeDate >= dateFrom
        }

        response = make_api_request(url, params, delay=60.0)

        if response.status_code == 200:
            orders_batch = response.json()
            print(f"✅ Получено {len(orders_batch)} заказов в этом запросе")

            if not orders_batch:
                print("✅ Все заказы выгружены")
                break

            all_orders.extend(orders_batch)

            # Берем lastChangeDate из последней записи для следующего запроса
            last_order = orders_batch[-1]
            current_date_from = last_order['lastChangeDate']

            # Если получено мало записей, вероятно это последняя страница
            if len(orders_batch) < 1000:
                print("✅ Получены все заказы (маленькая партия)")
                break

        else:
            print(f"❌ Ошибка получения заказов: {response.status_code} - {response.text}")
            break

    print(f"📊 Итого получено заказов: {len(all_orders)}")
    return all_orders


def get_orders_by_date(date_from, flag=1):
    """
    Получение заказов за конкретную дату (flag=1)
    """
    url = f"{STAT_URL}/api/v1/supplier/orders"
    params = {
        'dateFrom': date_from,
        'flag': flag  # flag=1 для получения всех заказов за указанную дату
    }

    print(f"📦 Запрос заказов за {date_from} (flag={flag})...")
    response = make_api_request(url, params, delay=60.0)

    if response.status_code == 200:
        orders = response.json()
        print(f"✅ Получено {len(orders)} заказов за {date_from}")
        return orders
    else:
        print(f"❌ Ошибка получения заказов: {response.status_code} - {response.text}")
        return None


def get_incomes(date_from=None):
    """
    Получение данных о поставках
    """
    if date_from is None:
        date_from = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')

    url = f"{STAT_URL}/api/v1/supplier/incomes"
    params = {
        'dateFrom': date_from
    }

    print(f"🚚 Запрос поставок с {date_from}...")
    response = make_api_request(url, params, delay=60.0)

    if response.status_code == 200:
        incomes = response.json()
        print(f"✅ Получено {len(incomes)} поставок")
        return incomes
    else:
        print(f"❌ Ошибка получения поставок: {response.status_code} - {response.text}")
        return None


def get_stocks(date_from=None):
    """
    Получение информации об остатках на складах
    """
    if date_from is None:
        date_from = datetime.now().strftime('%Y-%m-%d')

    url = f"{STAT_URL}/api/v1/supplier/stocks"
    params = {
        'dateFrom': date_from
    }

    print(f"📦 Запрос остатков с {date_from}...")
    response = make_api_request(url, params, delay=60.0)

    if response.status_code == 200:
        stocks = response.json()
        print(f"✅ Получено {len(stocks)} записей об остатках")
        return stocks
    else:
        print(f"❌ Ошибка получения остатков: {response.status_code} - {response.text}")
        return None


def get_sales(date_from=None, flag=1):
    """
    Получение продаж за указанную дату
    """
    if date_from is None:
        date_from = datetime.now().strftime('%Y-%m-%d')

    url = f"{STAT_URL}/api/v1/supplier/sales"
    params = {
        'dateFrom': date_from,
        'flag': flag
    }

    print(f"💰 Запрос продаж за {date_from} (flag={flag})...")
    response = make_api_request(url, params, delay=60.0)

    if response.status_code == 200:
        sales = response.json()
        print(f"✅ Получено {len(sales)} продаж")
        return sales
    else:
        print(f"❌ Ошибка получения продаж: {response.status_code} - {response.text}")
        return None


def analyze_orders_stats(orders_data):
    """
    Анализ статистики по заказам
    """
    if not orders_data:
        return {
            'total_orders': 0,
            'total_amount': 0,
            'canceled_orders': 0,
            'valid_orders': 0,
            'valid_amount': 0,
            'warehouses': {},
            'categories': {}
        }

    total_orders = len(orders_data)
    total_amount = sum(order.get('totalPrice', 0) for order in orders_data)

    # Неотмененные заказы
    valid_orders = [order for order in orders_data if not order.get('isCancel', False)]
    canceled_orders = [order for order in orders_data if order.get('isCancel', False)]

    valid_amount = sum(order.get('priceWithDisc', 0) for order in valid_orders)

    # Статистика по складам
    warehouses = {}
    for order in valid_orders:
        warehouse = order.get('warehouseName', 'Не указан')
        if warehouse not in warehouses:
            warehouses[warehouse] = {'count': 0, 'amount': 0}
        warehouses[warehouse]['count'] += 1
        warehouses[warehouse]['amount'] += order.get('priceWithDisc', 0)

    # Статистика по категориям
    categories = {}
    for order in valid_orders:
        category = order.get('category', 'Не указана')
        if category not in categories:
            categories[category] = {'count': 0, 'amount': 0}
        categories[category]['count'] += 1
        categories[category]['amount'] += order.get('priceWithDisc', 0)

    return {
        'total_orders': total_orders,
        'total_amount': total_amount,
        'canceled_orders': len(canceled_orders),
        'valid_orders': len(valid_orders),
        'valid_amount': valid_amount,
        'warehouses': warehouses,
        'categories': categories
    }


def analyze_sales_stats(sales_data):
    """
    Анализ статистики по продажам
    """
    if not sales_data:
        return {
            'total_sales': 0,
            'total_amount': 0,
            'realized_sales': 0,
            'realized_amount': 0
        }

    total_sales = len(sales_data)
    total_amount = sum(sale.get('totalPrice', 0) for sale in sales_data)

    # Реализованные продажи (выкупы)
    realized_sales = [sale for sale in sales_data if sale.get('isRealization', False)]
    realized_amount = sum(sale.get('finishedPrice', 0) for sale in realized_sales)

    return {
        'total_sales': total_sales,
        'total_amount': total_amount,
        'realized_sales': len(realized_sales),
        'realized_amount': realized_amount
    }


def display_orders_dashboard(orders_stats, sales_stats):
    """
    Отображение сводной статистики
    """
    print("\n" + "=" * 70)
    print("📊 СВОДНАЯ СТАТИСТИКА FBO WILDBERRIES")
    print("=" * 70)

    print(f"\n🛒 ЗАКАЗЫ:")
    print(f"   Всего заказов: {orders_stats['total_orders']} шт.")
    print(f"   Неотмененных: {orders_stats['valid_orders']} шт.")
    print(f"   Отмененных: {orders_stats['canceled_orders']} шт.")
    print(f"   Сумма неотмененных: {orders_stats['valid_amount']:,.0f} руб.")

    print(f"\n💰 ПРОДАЖИ:")
    print(f"   Всего операций: {sales_stats['total_sales']} шт.")
    print(f"   Выкупов: {sales_stats['realized_sales']} шт.")
    print(f"   Сумма выкупов: {sales_stats['realized_amount']:,.0f} руб.")

    if orders_stats['warehouses']:
        print(f"\n🏭 ЗАКАЗЫ ПО СКЛАДАМ:")
        for warehouse, data in list(orders_stats['warehouses'].items())[:5]:
            print(f"   {warehouse}: {data['count']} шт. / {data['amount']:,.0f} руб.")

    if orders_stats['categories']:
        print(f"\n📦 ТОП КАТЕГОРИЙ:")
        sorted_categories = sorted(orders_stats['categories'].items(),
                                   key=lambda x: x[1]['amount'], reverse=True)
        for category, data in sorted_categories[:5]:
            print(f"   {category}: {data['count']} шт. / {data['amount']:,.0f} руб.")


def get_24h_orders_stats():
    """
    Получение статистики за последние 24 часа
    """
    now = datetime.now()
    date_24h_ago = (now - timedelta(hours=24)).strftime('%Y-%m-%dT%H:%M:%S')

    print(f"🕐 Получение заказов за последние 24 часа (с {date_24h_ago})")

    # Получаем все заказы с пагинацией
    orders = get_all_orders(date_24h_ago)

    # Фильтруем за последние 24 часа по lastChangeDate
    filtered_orders = []
    for order in orders:
        last_change_str = order.get('lastChangeDate')
        if last_change_str:
            try:
                last_change = datetime.fromisoformat(last_change_str.replace('Z', '+00:00'))
                if now - timedelta(hours=24) <= last_change <= now:
                    filtered_orders.append(order)
            except (ValueError, AttributeError):
                continue

    return filtered_orders


def main():
    """
    Главная функция сбора статистики
    """
    print("=== ПОЛНАЯ СТАТИСТИКА FBO WILDBERRIES ===")
    print(f"📅 Дата анализа: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    try:
        # Вариант 1: Статистика за последние 24 часа с пагинацией
        print("\n1. 📊 СТАТИСТИКА ЗА ПОСЛЕДНИЕ 24 ЧАСА")
        recent_orders = get_24h_orders_stats()

        # Вариант 2: Данные за сегодня
        print("\n2. 📊 СТАТИСТИКА ЗА СЕГОДНЯ")
        today = datetime.now().strftime('%Y-%m-%d')
        today_orders = get_orders_by_date(today, flag=1)
        time.sleep(60)

        today_sales = get_sales(today, flag=1)
        time.sleep(60)

        # Вариант 3: Данные за вчера для сравнения
        print("\n3. 📊 СТАТИСТИКА ЗА ВЧЕРА")
        yesterday = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
        yesterday_orders = get_orders_by_date(yesterday, flag=1)
        time.sleep(60)

        yesterday_sales = get_sales(yesterday, flag=1)

        # Анализ статистики
        print("\n4. 📈 АНАЛИЗ ДАННЫХ")
        today_orders_stats = analyze_orders_stats(today_orders or [])
        today_sales_stats = analyze_sales_stats(today_sales or [])

        # Отображение результатов
        display_orders_dashboard(today_orders_stats, today_sales_stats)

        # Дополнительная информация
        print(f"\n💡 ИНФОРМАЦИЯ:")
        print(f"   • Данные обновляются раз в 30 минут")
        print(f"   • Лимит: 1 запрос в минуту")
        print(f"   • Данные хранятся 90 дней")
        print(f"   • Для точного определения заказа используйте поле srid")

    except Exception as e:
        print(f"❌ Ошибка при сборе статистики: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()