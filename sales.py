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


def get_all_sales(date_from, max_requests=10):
    """
    Получение всех продаж с пагинацией согласно документации
    """
    all_sales = []
    current_date_from = date_from

    for request_num in range(max_requests):
        print(f"💰 Запрос продаж #{request_num + 1} с dateFrom: {current_date_from}")

        url = f"{STAT_URL}/api/v1/supplier/sales"
        params = {
            'dateFrom': current_date_from,
            'flag': 0  # Данные с lastChangeDate >= dateFrom
        }

        response = make_api_request(url, params, delay=60.0)

        if response.status_code == 200:
            sales_batch = response.json()
            print(f"✅ Получено {len(sales_batch)} продаж в этом запросе")

            if not sales_batch:
                print("✅ Все продажи выгружены")
                break

            all_sales.extend(sales_batch)

            # Берем lastChangeDate из последней записи для следующего запроса
            last_sale = sales_batch[-1]
            current_date_from = last_sale['lastChangeDate']

            # Если получено мало записей, вероятно это последняя страница
            if len(sales_batch) < 1000:
                print("✅ Получены все продажи (маленькая партия)")
                break

        else:
            print(f"❌ Ошибка получения продаж: {response.status_code} - {response.text}")
            break

    print(f"📊 Итого получено продаж: {len(all_sales)}")
    return all_sales


def get_sales_by_date(date_from, flag=1):
    """
    Получение продаж за конкретную дату (flag=1)
    """
    url = f"{STAT_URL}/api/v1/supplier/sales"
    params = {
        'dateFrom': date_from,
        'flag': flag  # flag=1 для получения всех продаж за указанную дату
    }

    print(f"💰 Запрос продаж за {date_from} (flag={flag})...")
    response = make_api_request(url, params, delay=60.0)

    if response.status_code == 200:
        sales = response.json()
        print(f"✅ Получено {len(sales)} продаж за {date_from}")
        return sales
    else:
        print(f"❌ Ошибка получения продаж: {response.status_code} - {response.text}")
        return None


def get_all_orders(date_from, max_requests=10):
    """
    Получение всех заказов с пагинацией
    """
    all_orders = []
    current_date_from = date_from

    for request_num in range(max_requests):
        print(f"📦 Запрос заказов #{request_num + 1} с dateFrom: {current_date_from}")

        url = f"{STAT_URL}/api/v1/supplier/orders"
        params = {
            'dateFrom': current_date_from,
            'flag': 0
        }

        response = make_api_request(url, params, delay=60.0)

        if response.status_code == 200:
            orders_batch = response.json()
            print(f"✅ Получено {len(orders_batch)} заказов в этом запросе")

            if not orders_batch:
                print("✅ Все заказы выгружены")
                break

            all_orders.extend(orders_batch)
            last_order = orders_batch[-1]
            current_date_from = last_order['lastChangeDate']

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
    Получение заказов за конкретную дату
    """
    url = f"{STAT_URL}/api/v1/supplier/orders"
    params = {
        'dateFrom': date_from,
        'flag': flag
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


def analyze_sales_detailed_stats(sales_data):
    """
    Детальный анализ статистики продаж согласно документации
    """
    if not sales_data:
        return {
            'total_operations': 0,
            'sales_count': 0,
            'returns_count': 0,
            'sales_amount': 0,
            'returns_amount': 0,
            'for_pay_total': 0,
            'finished_price_total': 0,
            'warehouses': {},
            'categories': {},
            'realization_stats': {
                'realized_count': 0,
                'realized_amount': 0,
                'not_realized_count': 0,
                'not_realized_amount': 0
            }
        }

    total_operations = len(sales_data)

    # Разделяем на продажи и возвраты по полю isRealization
    sales = [sale for sale in sales_data if sale.get('isRealization', False)]
    returns = [sale for sale in sales_data if not sale.get('isRealization', False)]

    # Финансовые показатели для продаж
    sales_amount = sum(sale.get('forPay', sale.get('finishedPrice', 0)) for sale in sales)
    returns_amount = sum(sale.get('forPay', sale.get('finishedPrice', 0)) for sale in returns)

    # Общие суммы по ключевым полям
    for_pay_total = sum(sale.get('forPay', 0) for sale in sales_data)
    finished_price_total = sum(sale.get('finishedPrice', 0) for sale in sales_data)
    price_with_disc_total = sum(sale.get('priceWithDisc', 0) for sale in sales_data)

    # Статистика по складам
    warehouses = {}
    for sale in sales_data:
        warehouse = sale.get('warehouseName', 'Не указан')
        if warehouse not in warehouses:
            warehouses[warehouse] = {
                'count': 0,
                'sales_count': 0,
                'returns_count': 0,
                'amount': 0
            }
        warehouses[warehouse]['count'] += 1
        if sale.get('isRealization', False):
            warehouses[warehouse]['sales_count'] += 1
        else:
            warehouses[warehouse]['returns_count'] += 1
        warehouses[warehouse]['amount'] += sale.get('forPay', sale.get('finishedPrice', 0))

    # Статистика по категориям
    categories = {}
    for sale in sales_data:
        category = sale.get('category', 'Не указана')
        if category not in categories:
            categories[category] = {
                'count': 0,
                'sales_count': 0,
                'returns_count': 0,
                'amount': 0
            }
        categories[category]['count'] += 1
        if sale.get('isRealization', False):
            categories[category]['sales_count'] += 1
        else:
            categories[category]['returns_count'] += 1
        categories[category]['amount'] += sale.get('forPay', sale.get('finishedPrice', 0))

    # Детальная статистика по реализации
    realization_stats = {
        'realized_count': len(sales),
        'realized_amount': sales_amount,
        'not_realized_count': len(returns),
        'not_realized_amount': returns_amount
    }

    return {
        'total_operations': total_operations,
        'sales_count': len(sales),
        'returns_count': len(returns),
        'sales_amount': sales_amount,
        'returns_amount': returns_amount,
        'for_pay_total': for_pay_total,
        'finished_price_total': finished_price_total,
        'price_with_disc_total': price_with_disc_total,
        'warehouses': warehouses,
        'categories': categories,
        'realization_stats': realization_stats
    }


def analyze_orders_stats(orders_data):
    """
    Анализ статистики по заказам
    """
    if not orders_data:
        return {
            'total_orders': 0,
            'valid_orders': 0,
            'canceled_orders': 0,
            'valid_amount': 0,
            'warehouses': {},
            'categories': {}
        }

    total_orders = len(orders_data)
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
        'valid_orders': len(valid_orders),
        'canceled_orders': len(canceled_orders),
        'valid_amount': valid_amount,
        'warehouses': warehouses,
        'categories': categories
    }


def get_24h_sales_stats():
    """
    Получение статистики продаж за последние 24 часа
    """
    now = datetime.now()
    date_24h_ago = (now - timedelta(hours=24)).strftime('%Y-%m-%dT%H:%M:%S')

    print(f"🕐 Получение продаж за последние 24 часа (с {date_24h_ago})")

    # Получаем все продажи с пагинацией
    sales = get_all_sales(date_24h_ago)

    # Фильтруем за последние 24 часа по lastChangeDate
    filtered_sales = []
    for sale in sales:
        last_change_str = sale.get('lastChangeDate')
        if last_change_str:
            try:
                last_change = datetime.fromisoformat(last_change_str.replace('Z', '+00:00'))
                if now - timedelta(hours=24) <= last_change <= now:
                    filtered_sales.append(sale)
            except (ValueError, AttributeError):
                continue

    return filtered_sales


def display_sales_dashboard(sales_stats, orders_stats, period_name="Сегодня"):
    """
    Отображение сводной статистики продаж и заказов
    """
    print("\n" + "=" * 80)
    print(f"📊 СВОДНАЯ СТАТИСТИКА FBO WILDBERRIES - {period_name}")
    print("=" * 80)

    print(f"\n🛒 ЗАКАЗЫ:")
    print(f"   Всего заказов: {orders_stats['total_orders']} шт.")
    print(f"   Неотмененных: {orders_stats['valid_orders']} шт.")
    print(f"   Отмененных: {orders_stats['canceled_orders']} шт.")
    print(f"   Сумма неотмененных: {orders_stats['valid_amount']:,.0f} руб.")

    print(f"\n💰 ПРОДАЖИ И ВОЗВРАТЫ:")
    print(f"   Всего операций: {sales_stats['total_operations']} шт.")
    print(f"   Продажи (выкупы): {sales_stats['sales_count']} шт. / {sales_stats['sales_amount']:,.0f} руб.")
    print(f"   Возвраты: {sales_stats['returns_count']} шт. / {sales_stats['returns_amount']:,.0f} руб.")
    print(f"   Сумма к перечислению: {sales_stats['for_pay_total']:,.0f} руб.")
    print(f"   Финальная цена: {sales_stats['finished_price_total']:,.0f} руб.")

    if sales_stats['warehouses']:
        print(f"\n🏭 ПРОДАЖИ ПО СКЛАДАМ:")
        for warehouse, data in list(sales_stats['warehouses'].items())[:5]:
            print(f"   {warehouse}: {data['sales_count']} продаж / {data['returns_count']} возвратов")

    if sales_stats['categories']:
        print(f"\n📦 ТОП КАТЕГОРИЙ ПО ПРОДАЖАМ:")
        sorted_categories = sorted(sales_stats['categories'].items(),
                                   key=lambda x: x[1]['sales_count'], reverse=True)
        for category, data in sorted_categories[:5]:
            print(f"   {category}: {data['sales_count']} продаж / {data['returns_count']} возвратов")


def compare_periods_stats():
    """
    Сравнение статистики между текущим и предыдущим периодом
    """
    now = datetime.now()
    today = now.strftime('%Y-%m-%d')
    yesterday = (now - timedelta(days=1)).strftime('%Y-%m-%d')

    print("🔄 СРАВНЕНИЕ СТАТИСТИКИ ПО ПЕРИОДАМ")

    # Данные за сегодня
    print(f"\n📊 Загрузка данных за {today}...")
    today_sales = get_sales_by_date(today, flag=1)
    time.sleep(60)

    today_orders = get_orders_by_date(today, flag=1)
    time.sleep(60)

    # Данные за вчера
    print(f"\n📊 Загрузка данных за {yesterday}...")
    yesterday_sales = get_sales_by_date(yesterday, flag=1)
    time.sleep(60)

    yesterday_orders = get_orders_by_date(yesterday, flag=1)

    # Анализ статистики
    today_sales_stats = analyze_sales_detailed_stats(today_sales or [])
    today_orders_stats = analyze_orders_stats(today_orders or [])
    yesterday_sales_stats = analyze_sales_detailed_stats(yesterday_sales or [])
    yesterday_orders_stats = analyze_orders_stats(yesterday_orders or [])

    # Расчет разниц
    sales_diff = {
        'sales_count': today_sales_stats['sales_count'] - yesterday_sales_stats['sales_count'],
        'sales_amount': today_sales_stats['sales_amount'] - yesterday_sales_stats['sales_amount'],
        'returns_count': today_sales_stats['returns_count'] - yesterday_sales_stats['returns_count']
    }

    orders_diff = {
        'valid_orders': today_orders_stats['valid_orders'] - yesterday_orders_stats['valid_orders'],
        'valid_amount': today_orders_stats['valid_amount'] - yesterday_orders_stats['valid_amount']
    }

    return {
        'today': {
            'sales': today_sales_stats,
            'orders': today_orders_stats
        },
        'yesterday': {
            'sales': yesterday_sales_stats,
            'orders': yesterday_orders_stats
        },
        'diff': {
            'sales': sales_diff,
            'orders': orders_diff
        }
    }


def main():
    """
    Главная функция сбора статистики
    """
    print("=== ПОЛНАЯ СТАТИСТИКА ПРОДАЖ FBO WILDBERRIES ===")
    print(f"📅 Дата анализа: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    try:
        # Вариант 1: Детальная статистика за сегодня
        print("\n1. 📊 ДЕТАЛЬНАЯ СТАТИСТИКА ЗА СЕГОДНЯ")
        today = datetime.now().strftime('%Y-%m-%d')
        today_sales = get_sales_by_date(today, flag=1)
        time.sleep(60)

        today_orders = get_orders_by_date(today, flag=1)
        time.sleep(60)

        # Анализ данных
        today_sales_stats = analyze_sales_detailed_stats(today_sales or [])
        today_orders_stats = analyze_orders_stats(today_orders or [])

        # Отображение результатов
        display_sales_dashboard(today_sales_stats, today_orders_stats, "Сегодня")

        # Вариант 2: Сравнение с вчерашним днем
        print("\n2. 📈 СРАВНЕНИЕ С ВЧЕРАШНИМ ДНЕМ")
        comparison_stats = compare_periods_stats()

        print(f"\n📊 ИЗМЕНЕНИЯ ПО СРАВНЕНИЮ С ВЧЕРА:")
        print(f"   Продажи: {comparison_stats['diff']['sales']['sales_count']:+,.0f} шт.")
        print(f"   Сумма продаж: {comparison_stats['diff']['sales']['sales_amount']:+,.0f} руб.")
        print(f"   Заказы: {comparison_stats['diff']['orders']['valid_orders']:+,.0f} шт.")

        # Вариант 3: Статистика за последние 24 часа с пагинацией
        print("\n3. 🕐 СТАТИСТИКА ЗА ПОСЛЕДНИЕ 24 ЧАСА (ПАГИНАЦИЯ)")
        recent_sales = get_24h_sales_stats()
        recent_sales_stats = analyze_sales_detailed_stats(recent_sales)

        print(f"\n📈 Продажи за 24ч: {recent_sales_stats['sales_count']} шт.")
        print(f"📈 Возвраты за 24ч: {recent_sales_stats['returns_count']} шт.")

        # Информация о данных
        print(f"\n💡 ИНФОРМАЦИЯ О ДАННЫХ:")
        print(f"   • Данные обновляются раз в 30 минут")
        print(f"   • Лимит: 1 запрос в минуту на endpoint")
        print(f"   • Данные хранятся 90 дней")
        print(f"   • 1 строка = 1 заказ = 1 сборочное задание")
        print(f"   • Для точного определения используйте поле srid")
        print(f"   • Продажи: isRealization=true, Возвраты: isRealization=false")

    except Exception as e:
        print(f"❌ Ошибка при сборе статистики: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()