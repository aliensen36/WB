import requests
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from config import config

# Базовые URL API
STATISTICS_URL = "https://statistics-api.wildberries.ru"

API_TOKEN = config.API_TOKEN

HEADERS = {
    "Authorization": API_TOKEN,
    "Content-Type": "application/json"
}

# Глобальная переменная для ограничения запросов
last_request_time = 0
REQUEST_DELAY = 1.0  # 1 секунда между запросами


def make_request(url: str, params: dict = None) -> Optional[dict]:
    """Безопасный запрос с учетом лимитов API"""
    global last_request_time

    # Соблюдаем лимиты запросов
    current_time = time.time()
    elapsed = current_time - last_request_time
    if elapsed < REQUEST_DELAY:
        time.sleep(REQUEST_DELAY - elapsed)

    try:
        response = requests.get(url, headers=HEADERS, params=params, timeout=30)
        last_request_time = time.time()

        if response.status_code == 200:
            return response.json()
        elif response.status_code == 429:
            print("⚠️ Превышен лимит запросов, жду 60 секунд...")
            time.sleep(60)
            return make_request(url, params)
        else:
            print(f"❌ Ошибка API {response.status_code}: {response.text}")
            return None

    except Exception as e:
        print(f"❌ Ошибка запроса: {e}")
        return None


def get_today_orders() -> List[Dict]:
    """Получает заказы за сегодня"""
    today = datetime.now().strftime('%Y-%m-%d')
    url = f"{STATISTICS_URL}/api/v1/supplier/orders"
    params = {"dateFrom": today, "flag": 0}

    print(f"📥 Загрузка заказов за {today}...")
    data = make_request(url, params)
    return data if data else []


def get_today_sales() -> List[Dict]:
    """Получает продажи за сегодня"""
    today = datetime.now().strftime('%Y-%m-%d')
    url = f"{STATISTICS_URL}/api/v1/supplier/sales"
    params = {"dateFrom": today, "flag": 0}

    print(f"📥 Загрузка продаж за {today}...")
    data = make_request(url, params)
    return data if data else []


def get_today_financial_report() -> List[Dict]:
    """Получает детальный финансовый отчет за сегодня"""
    today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    tomorrow_start = today_start + timedelta(days=1)

    def to_rfc3339(dt: datetime) -> str:
        """Конвертирует в RFC3339 с московским временем"""
        return dt.strftime("%Y-%m-%dT%H:%M:%S+03:00")

    url = f"{STATISTICS_URL}/api/v5/supplier/reportDetailByPeriod"

    all_data = []
    rrd_id = 0
    limit = 100000

    print(f"📥 Загрузка финансового отчета за {today_start.strftime('%Y-%m-%d')}...")

    while True:
        params = {
            "dateFrom": to_rfc3339(today_start),
            "dateTo": to_rfc3339(tomorrow_start),
            "limit": limit,
            "rrd_id": rrd_id,
            "period": "daily"
        }

        data = make_request(url, params)

        if not data or not isinstance(data, list):
            break

        if not data:
            break

        all_data.extend(data)
        print(f"   📋 Получено строк: {len(data)}, всего: {len(all_data)}")

        # Проверяем пагинацию
        if len(data) < limit:
            break

        # Получаем следующий rrd_id для пагинации
        last_item = data[-1]
        if "rrd_id" in last_item and last_item["rrd_id"]:
            new_rrd_id = int(last_item["rrd_id"])
            if new_rrd_id == rrd_id:
                break
            rrd_id = new_rrd_id
        else:
            break

    return all_data


def analyze_sales_data(sales_data: List[Dict]) -> Dict:
    """Анализирует данные о продажах"""
    total_sales_amount = 0.0
    total_sales_quantity = 0
    sales_by_brand = {}
    sales_by_category = {}

    for sale in sales_data:
        try:
            amount = float(sale.get('totalPrice', 0))
            quantity = int(sale.get('quantity', 0))
            brand = sale.get('brandName', 'Неизвестно')
            category = sale.get('subjectName', 'Неизвестно')

            total_sales_amount += amount
            total_sales_quantity += quantity

            # Статистика по брендам
            if brand not in sales_by_brand:
                sales_by_brand[brand] = {'amount': 0.0, 'quantity': 0}
            sales_by_brand[brand]['amount'] += amount
            sales_by_brand[brand]['quantity'] += quantity

            # Статистика по категориям
            if category not in sales_by_category:
                sales_by_category[category] = {'amount': 0.0, 'quantity': 0}
            sales_by_category[category]['amount'] += amount
            sales_by_category[category]['quantity'] += quantity

        except (ValueError, TypeError):
            continue

    return {
        'total_amount': round(total_sales_amount, 2),
        'total_quantity': total_sales_quantity,
        'count': len(sales_data),
        'avg_amount': round(total_sales_amount / len(sales_data), 2) if sales_data else 0,
        'by_brand': sales_by_brand,
        'by_category': sales_by_category
    }


def analyze_orders_data(orders_data: List[Dict]) -> Dict:
    """Анализирует данные о заказах"""
    new_orders = [o for o in orders_data if not o.get('isCancel', False)]
    canceled_orders = [o for o in orders_data if o.get('isCancel', False)]

    total_orders_amount = sum(float(o.get('totalPrice', 0)) for o in new_orders)
    avg_order_amount = total_orders_amount / len(new_orders) if new_orders else 0

    return {
        'total': len(orders_data),
        'new': len(new_orders),
        'canceled': len(canceled_orders),
        'total_amount': round(total_orders_amount, 2),
        'avg_amount': round(avg_order_amount, 2)
    }


def analyze_buyouts_data(financial_data: List[Dict]) -> Dict:
    """Анализирует данные о выкупах (реальных продажах)"""
    buyouts = []
    total_buyouts_amount = 0.0
    total_buyouts_quantity = 0
    buyouts_by_brand = {}
    buyouts_by_category = {}

    for row in financial_data:
        try:
            # Критерии выкупа из рекомендаций сообщества WB
            sa_name = row.get('sa_name')
            operation_type = row.get('supplier_oper_name')
            doc_type = row.get('doc_type_name')

            is_buyout = (
                    sa_name is not None and
                    sa_name != "" and
                    operation_type == "Продажа" and
                    doc_type == "Продажа"
            )

            if is_buyout:
                # Сумма выкупа
                amount = 0.0
                if row.get('ppvz_for_pay'):
                    amount = float(row['ppvz_for_pay'])
                elif row.get('retail_price_withdisc_rub'):
                    amount = float(row['retail_price_withdisc_rub'])

                quantity = int(row.get('quantity', 0))
                brand = row.get('brand_name', 'Неизвестно')
                category = row.get('subject_name', 'Неизвестно')

                buyouts.append(row)
                total_buyouts_amount += amount
                total_buyouts_quantity += quantity

                # Статистика по брендам
                if brand not in buyouts_by_brand:
                    buyouts_by_brand[brand] = {'amount': 0.0, 'quantity': 0}
                buyouts_by_brand[brand]['amount'] += amount
                buyouts_by_brand[brand]['quantity'] += quantity

                # Статистика по категориям
                if category not in buyouts_by_category:
                    buyouts_by_category[category] = {'amount': 0.0, 'quantity': 0}
                buyouts_by_category[category]['amount'] += amount
                buyouts_by_category[category]['quantity'] += quantity

        except (ValueError, TypeError):
            continue

    return {
        'count': len(buyouts),
        'total_amount': round(total_buyouts_amount, 2),
        'total_quantity': total_buyouts_quantity,
        'avg_amount': round(total_buyouts_amount / len(buyouts), 2) if buyouts else 0,
        'by_brand': buyouts_by_brand,
        'by_category': buyouts_by_category
    }


def display_comprehensive_report(orders_data: List[Dict], sales_data: List[Dict], financial_data: List[Dict]):
    """Отображает комплексный отчет в формате ЛК"""
    today = datetime.now().strftime('%Y-%m-%d')

    # Анализ данных
    orders_analysis = analyze_orders_data(orders_data)
    sales_analysis = analyze_sales_data(sales_data)
    buyouts_analysis = analyze_buyouts_data(financial_data)

    print(f"\n{'=' * 80}")
    print(f"📊 ОТЧЕТ ПО ПРОДАЖАМ И ВЫКУПАМ ЗА {today}")
    print(f"{'=' * 80}")

    print(f"\n🛒 ЗАКАЗЫ (новые за сегодня):")
    print(f"   📦 Всего заказов: {orders_analysis['total']:,}")
    print(f"   ✅ Новых: {orders_analysis['new']:,}")
    print(f"   ❌ Отменено: {orders_analysis['canceled']:,}")
    print(f"   💰 Сумма заказов: {orders_analysis['total_amount']:,.2f} руб.")
    print(f"   📊 Средний заказ: {orders_analysis['avg_amount']:,.2f} руб.")

    print(f"\n💰 ПРОДАЖИ (все операции за сегодня):")
    print(f"   📄 Документов: {sales_analysis['count']:,}")
    print(f"   🏷️ Товаров: {sales_analysis['total_quantity']:,} шт.")
    print(f"   💰 Сумма продаж: {sales_analysis['total_amount']:,.2f} руб.")
    print(f"   📊 Средний чек: {sales_analysis['avg_amount']:,.2f} руб.")

    print(f"\n✅ ВЫКУПЫ (реальные продажи за сегодня):")
    print(f"   📄 Документов: {buyouts_analysis['count']:,}")
    print(f"   🏷️ Товаров: {buyouts_analysis['total_quantity']:,} шт.")
    print(f"   💰 Сумма выкупа: {buyouts_analysis['total_amount']:,.2f} руб.")
    print(f"   📊 Средний выкуп: {buyouts_analysis['avg_amount']:,.2f} руб.")

    # Анализ эффективности
    print(f"\n📈 АНАЛИЗ ЭФФЕКТИВНОСТИ:")
    if orders_analysis['new'] > 0:
        conversion_rate = (buyouts_analysis['count'] / orders_analysis['new']) * 100
        print(f"   🎯 Конверсия в выкупы: {conversion_rate:.1f}%")

    if sales_analysis['total_amount'] > 0:
        buyout_share = (buyouts_analysis['total_amount'] / sales_analysis['total_amount']) * 100
        print(f"   📊 Доля выкупов: {buyout_share:.1f}%")

    # Топ брендов по выкупам
    if buyouts_analysis['by_brand']:
        print(f"\n🏆 ТОП БРЕНДЫ ПО ВЫКУПАМ:")
        top_brands = sorted(
            buyouts_analysis['by_brand'].items(),
            key=lambda x: x[1]['amount'],
            reverse=True
        )[:5]

        for brand, stats in top_brands:
            print(f"   • {brand}: {stats['quantity']} шт., {stats['amount']:,.2f} руб.")

    # Топ категорий по выкупам
    if buyouts_analysis['by_category']:
        print(f"\n📦 ТОП КАТЕГОРИИ ПО ВЫКУПАМ:")
        top_categories = sorted(
            buyouts_analysis['by_category'].items(),
            key=lambda x: x[1]['amount'],
            reverse=True
        )[:5]

        for category, stats in top_categories:
            print(f"   • {category}: {stats['quantity']} шт., {stats['amount']:,.2f} руб.")

    # Сводка по дням (если есть исторические данные)
    print(f"\n💡 СВОДКА:")
    print(f"   📅 Дата отчета: {today}")
    print(f"   ⏰ Время формирования: {datetime.now().strftime('%H:%M:%S')}")
    print(f"   📊 Источники данных: API Wildberries (FBO)")


def main():
    """Основная функция получения отчета"""
    print("🚀 Запуск сбора данных за сегодня")
    print("💡 Источник: API Wildberries FBO")
    print("📊 Формат: полностью соответствует личному кабинету")

    # Получаем данные
    orders_data = get_today_orders()
    sales_data = get_today_sales()
    financial_data = get_today_financial_report()

    # Проверяем наличие данных
    if not any([orders_data, sales_data, financial_data]):
        print("\n❌ Нет данных за сегодня")
        print("💡 Возможные причины:")
        print("   • Сегодня еще не было операций")
        print("   • Данные обновляются с задержкой")
        print("   • Проверьте настройки API токена")
        return

    # Формируем отчет
    display_comprehensive_report(orders_data, sales_data, financial_data)

    print(f"\n{'=' * 80}")
    print("✅ ОТЧЕТ ЗАВЕРШЕН")
    print(f"{'=' * 80}")


if __name__ == "__main__":
    main()