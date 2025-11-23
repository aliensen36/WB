from datetime import datetime


def format_stats_response(orders_stats, sales_stats, period):
    """Форматирует статистику в красивый текст"""

    text = f"📊 <b>СТАТИСТИКА ЗА {period.upper()}</b>\n\n"

    text += f"🛒 <b>ЗАКАЗЫ:</b>\n"
    text += f"   • Всего: {orders_stats['total_orders']} шт.\n"
    text += f"   • Неотмененных: {orders_stats['valid_orders']} шт.\n"
    text += f"   • Отмененных: {orders_stats['canceled_orders']} шт.\n"
    text += f"   • Сумма: {orders_stats['valid_amount']:,.0f} руб.\n\n"

    text += f"💰 <b>ПРОДАЖИ:</b>\n"
    text += f"   • Операций: {sales_stats['total_sales']} шт.\n"
    text += f"   • Выкупов: {sales_stats['realized_sales']} шт.\n"
    text += f"   • Сумма: {sales_stats['realized_amount']:,.0f} руб.\n\n"

    if orders_stats['warehouses']:
        text += f"🏭 <b>ТОП СКЛАДОВ:</b>\n"
        for warehouse, data in list(orders_stats['warehouses'].items())[:3]:
            text += f"   • {warehouse}: {data['count']} шт. / {data['amount']:,.0f} руб.\n"
        text += "\n"

    if orders_stats['categories']:
        text += f"📦 <b>ТОП КАТЕГОРИЙ:</b>\n"
        sorted_categories = sorted(orders_stats['categories'].items(),
                                   key=lambda x: x[1]['amount'], reverse=True)
        for category, data in sorted_categories[:3]:
            text += f"   • {category}: {data['count']} шт. / {data['amount']:,.0f} руб.\n"

    text += f"\n⏰ <i>Обновлено: {datetime.now().strftime('%H:%M')}</i>"

    return text


def format_incomes_response(incomes):
    """Форматирует данные о поставках"""
    if not incomes:
        return "🚚 <b>ДАННЫЕ О ПОСТАВКАХ</b>\n\nНет данных о поставках за последние 30 дней."

    total_incomes = len(incomes)
    # Группируем по статусу
    status_counts = {}
    for income in incomes:
        status = income.get('status', 'Неизвестно')
        status_counts[status] = status_counts.get(status, 0) + 1

    text = f"🚚 <b>ДАННЫЕ О ПОСТАВКАХ</b>\n\n"
    text += f"📦 Всего поставок: {total_incomes}\n\n"
    text += f"📊 <b>По статусам:</b>\n"

    for status, count in status_counts.items():
        text += f"   • {status}: {count} шт.\n"

    # Последние 5 поставок
    recent_incomes = sorted(incomes, key=lambda x: x.get('date', ''), reverse=True)[:5]
    text += f"\n📋 <b>Последние поставки:</b>\n"
    for income in recent_incomes:
        date = income.get('date', 'Неизвестно')
        income_id = income.get('incomeId', 'N/A')
        text += f"   • {date} (ID: {income_id})\n"

    return text


def format_stocks_response(stocks):
    """Форматирует данные об остатках"""
    if not stocks:
        return "📦 <b>ДАННЫЕ ОБ ОСТАТКАХ</b>\n\nНет данных об остатках."

    total_stocks = len(stocks)
    total_quantity = sum(stock.get('quantity', 0) for stock in stocks)

    # Группируем по складам
    warehouse_stocks = {}
    for stock in stocks:
        warehouse = stock.get('warehouseName', 'Неизвестно')
        if warehouse not in warehouse_stocks:
            warehouse_stocks[warehouse] = 0
        warehouse_stocks[warehouse] += stock.get('quantity', 0)

    text = f"📦 <b>ДАННЫЕ ОБ ОСТАТКАХ</b>\n\n"
    text += f"📊 Всего SKU: {total_stocks}\n"
    text += f"📦 Общее количество: {total_quantity} шт.\n\n"
    text += f"🏭 <b>Распределение по складам:</b>\n"

    for warehouse, quantity in warehouse_stocks.items():
        text += f"   • {warehouse}: {quantity} шт.\n"

    return text
