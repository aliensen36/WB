# sales_funnel_today.py
import requests
import json
from datetime import datetime, timedelta
import time
import os
from config import Config


def get_today_date():
    """
    Возвращает текущую дату в формате YYYY-MM-DD
    """
    return datetime.now().strftime("%Y-%m-%d")


def fetch_sales_funnel_data_today(api_token, start_date, end_date):
    """
    Получение данных воронки продаж за сегодня

    Args:
        api_token (str): API токен Wildberries
        start_date (str): Начало периода в формате YYYY-MM-DD (сегодня)
        end_date (str): Конец периода в формате YYYY-MM-DD (сегодня)

    Returns:
        list: Список всех товаров с данными за период
    """
    url = "https://seller-analytics-api.wildberries.ru/api/analytics/v3/sales-funnel/products"

    headers = {
        "Authorization": api_token,
        "accept": "application/json",
        "Content-Type": "application/json"
    }

    # Основной период - сегодня
    selected_period = {
        "start": start_date,
        "end": end_date
    }

    all_products = []
    limit = 1000  # Максимальное количество записей за один запрос
    offset = 0

    print(f"📅 Запрашиваем данные за сегодня: {start_date}")

    try:
        while True:
            # Формируем тело запроса с пагинацией
            # НЕ используем pastPeriod, так как он вызывает ошибку для сегодняшней даты
            payload = {
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

            print(f"📤 Отправка запроса: offset={offset}, limit={limit}")

            try:
                response = requests.post(url, headers=headers, json=payload, timeout=30)
            except requests.exceptions.Timeout:
                print("⏰ Таймаут запроса. Повтор через 10 секунд...")
                time.sleep(10)
                continue
            except requests.exceptions.ConnectionError:
                print("🔌 Ошибка соединения. Повтор через 10 секунд...")
                time.sleep(10)
                continue

            # Проверка статуса ответа
            if response.status_code == 200:
                data = response.json()

                # Проверяем наличие данных
                if "data" in data and "products" in data["data"]:
                    products = data["data"]["products"]

                    if not products:
                        print("✅ Все данные получены. Пустой список товаров.")
                        break

                    all_products.extend(products)
                    print(f"✅ Получено {len(products)} товаров. Всего: {len(all_products)}")

                    # Если получено меньше товаров чем лимит, значит это последняя страница
                    if len(products) < limit:
                        print(f"✅ Все страницы загружены. Итого товаров: {len(all_products)}")
                        break

                    # Увеличиваем offset для следующей страницы
                    offset += limit

                    # Добавляем задержку для соблюдения лимитов API (3 запроса в минуту)
                    print("⏳ Ожидание 20 секунд для соблюдения лимита API...")
                    time.sleep(20)
                else:
                    print("⚠️ Неожиданная структура ответа API")
                    if Config.DEBUG:
                        print(f"Ответ: {json.dumps(data, indent=2, ensure_ascii=False)[:500]}...")
                    break

            elif response.status_code == 429:
                print("⚠️ Превышен лимит запросов. Ожидание 60 секунд...")
                time.sleep(60)
                continue

            elif response.status_code == 400:
                error_data = response.json()
                print(f"❌ Ошибка 400: {error_data.get('title', 'Некорректный запрос')}")
                print(f"   Детали: {error_data.get('detail', 'Нет деталей')}")

                # Если ошибка связана с pastPeriod, пробуем без него
                if "past period" in error_data.get('detail', '').lower():
                    print("   Пробуем получить данные без сравнения с прошлым периодом...")
                    # Уже не используем pastPeriod, так что это не должно произойти
                    break
                else:
                    break

            elif response.status_code == 401:
                print("❌ Ошибка авторизации. Проверьте API токен.")
                print(f"   Ответ: {response.text[:200]}...")
                break

            elif response.status_code == 403:
                print("❌ Доступ запрещен. Проверьте права доступа API токена.")
                break

            else:
                print(f"❌ Ошибка API ({response.status_code}): {response.text[:200]}...")
                break

        return all_products

    except Exception as e:
        print(f"❌ Неожиданная ошибка: {e}")
        return []


def save_data_to_file(data, filename):
    """
    Сохранение данных в JSON файл

    Args:
        data (list): Данные для сохранения
        filename (str): Имя файла
    """
    try:
        # Создаем директорию если нужно
        os.makedirs(os.path.dirname(filename) if os.path.dirname(filename) else '.', exist_ok=True)

        # Формируем структуру с метаданными
        result = {
            "metadata": {
                "export_date": datetime.now().isoformat(),
                "export_timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "data_period": {
                    "start": data[0]["statistic"]["selected"]["period"]["start"] if data else None,
                    "end": data[0]["statistic"]["selected"]["period"]["end"] if data else None
                } if data else {},
                "total_items": len(data),
                "source": "Wildberries API - Воронка продаж",
                "api_endpoint": "POST /api/analytics/v3/sales-funnel/products"
            },
            "products": data
        }

        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(result, f, indent=2, ensure_ascii=False, default=str)

        file_size = os.path.getsize(filename) / 1024  # Размер в КБ

        print(f"💾 Данные сохранены в файл: {filename}")
        print(f"   📊 Всего записей: {len(data)}")
        print(f"   📦 Размер файла: {file_size:.1f} КБ")

        return True

    except Exception as e:
        print(f"❌ Ошибка при сохранении файла: {e}")
        return False


def calculate_daily_statistics(products):
    """
    Расчет и вывод статистики за день

    Args:
        products (list): Список товаров
    """
    if not products:
        print("📊 Нет данных для расчета статистики")
        return None

    total_stats = {
        'total_products': len(products),
        'total_open': 0,
        'total_cart': 0,
        'total_order': 0,
        'total_order_sum': 0,
        'total_buyout': 0,
        'products_with_orders': 0,
        'products_with_cart': 0,
        'top_products': []
    }

    # Собираем статистику по брендам
    brand_stats = {}

    for product in products:
        prod_info = product.get('product', {})
        stat_info = product.get('statistic', {}).get('selected', {})

        # Общая статистика
        open_count = stat_info.get('openCount', 0)
        cart_count = stat_info.get('cartCount', 0)
        order_count = stat_info.get('orderCount', 0)
        order_sum = stat_info.get('orderSum', 0)
        buyout_count = stat_info.get('buyoutCount', 0)

        total_stats['total_open'] += open_count
        total_stats['total_cart'] += cart_count
        total_stats['total_order'] += order_count
        total_stats['total_order_sum'] += order_sum
        total_stats['total_buyout'] += buyout_count

        if order_count > 0:
            total_stats['products_with_orders'] += 1
        if cart_count > 0:
            total_stats['products_with_cart'] += 1

        # Статистика по брендам
        brand = prod_info.get('brandName', 'Без бренда') or 'Без бренда'
        if brand not in brand_stats:
            brand_stats[brand] = {
                'products': 0,
                'orders': 0,
                'revenue': 0,
                'views': 0,
                'cart_adds': 0
            }
        brand_stats[brand]['products'] += 1
        brand_stats[brand]['orders'] += order_count
        brand_stats[brand]['revenue'] += order_sum
        brand_stats[brand]['views'] += open_count
        brand_stats[brand]['cart_adds'] += cart_count

        # Собираем топ товары
        if order_count > 0:
            total_stats['top_products'].append({
                'nmId': prod_info.get('nmId'),
                'title': prod_info.get('title', ''),
                'brand': brand,
                'orders': order_count,
                'revenue': order_sum,
                'views': open_count,
                'cart_adds': cart_count
            })

    return total_stats, brand_stats


def print_daily_report(products, filename):
    """
    Вывод ежедневного отчета

    Args:
        products (list): Список товаров
        filename (str): Имя файла с данными
    """
    if not products:
        print("\n" + "=" * 70)
        print("📅 ЕЖЕДНЕВНЫЙ ОТЧЕТ")
        print("=" * 70)
        print("ℹ️  Нет данных за сегодня")
        print("=" * 70)
        return

    stats, brand_stats = calculate_daily_statistics(products)

    print("\n" + "=" * 70)
    print("📅 ЕЖЕДНЕВНЫЙ ОТЧЕТ")
    print("=" * 70)
    print(f"📅 Дата: {get_today_date()}")
    print(f"⏰ Время выгрузки: {datetime.now().strftime('%H:%M:%S')}")
    print(f"💾 Файл данных: {filename}")
    print("=" * 70)

    print(f"\n📊 ОБЩАЯ СТАТИСТИКА:")
    print(f"   • Всего товаров в каталоге: {stats['total_products']:,}")
    print(f"   • Товаров с заказами: {stats['products_with_orders']:,}")
    print(f"   • Товаров в корзине: {stats['products_with_cart']:,}")
    print(f"   • Всего просмотров: {stats['total_open']:,}")
    print(f"   • Добавлений в корзину: {stats['total_cart']:,}")
    print(f"   • Заказов: {stats['total_order']:,}")
    print(f"   • Выручка: {stats['total_order_sum']:,} руб.")
    print(f"   • Выкупов: {stats['total_buyout']:,}")

    # Конверсии
    if stats['total_open'] > 0:
        conv_to_cart = (stats['total_cart'] / stats['total_open']) * 100
        print(f"\n📈 КОНВЕРСИИ:")
        print(f"   • Просмотр → Корзина: {conv_to_cart:.1f}%")

    if stats['total_cart'] > 0:
        conv_to_order = (stats['total_order'] / stats['total_cart']) * 100
        print(f"   • Корзина → Заказ: {conv_to_order:.1f}%")

    if stats['total_order'] > 0:
        avg_check = stats['total_order_sum'] / stats['total_order']
        buyout_rate = (stats['total_buyout'] / stats['total_order']) * 100
        print(f"   • Средний чек: {avg_check:,.0f} руб.")
        print(f"   • Процент выкупа: {buyout_rate:.1f}%")

    # Топ товаров
    if stats['top_products']:
        print(f"\n🏆 ТОП-5 ТОВАРОВ ПО ВЫРУЧКЕ:")
        top_by_revenue = sorted(stats['top_products'], key=lambda x: x['revenue'], reverse=True)[:5]

        for i, product in enumerate(top_by_revenue, 1):
            title = product['title']
            if len(title) > 40:
                title = title[:37] + "..."

            print(f"\n   {i}. {title}")
            print(f"      🔸 Артикул: {product['nmId']}")
            print(f"      🔸 Бренд: {product['brand']}")
            print(f"      🔸 Заказы: {product['orders']:,}")
            print(f"      🔸 Выручка: {product['revenue']:,} руб.")
            print(f"      🔸 Просмотры: {product['views']:,}")
            print(f"      🔸 В корзине: {product['cart_adds']:,}")

    # Статистика по брендам
    if len(brand_stats) > 1:
        print(f"\n🏷️  СТАТИСТИКА ПО БРЕНДАМ:")

        # Сортируем бренды по выручке
        sorted_brands = sorted(brand_stats.items(), key=lambda x: x[1]['revenue'], reverse=True)

        for brand, stats_data in sorted_brands[:5]:  # Топ-5 брендов
            if stats_data['revenue'] > 0:
                print(f"\n   {brand}:")
                print(f"      • Товаров: {stats_data['products']}")
                print(f"      • Заказов: {stats_data['orders']:,}")
                print(f"      • Выручка: {stats_data['revenue']:,} руб.")
                print(f"      • Просмотры: {stats_data['views']:,}")

                if stats_data['views'] > 0:
                    conv = (stats_data['cart_adds'] / stats_data['views']) * 100
                    print(f"      • Конверсия в корзину: {conv:.1f}%")

    print("\n" + "=" * 70)
    print("✅ ОТЧЕТ СФОРМИРОВАН")
    print("=" * 70)


def main():
    """Основная функция для получения данных за сегодня"""

    print("=" * 70)
    print("📊 WILDBERRIES - ВЫГРУЗКА ДАННЫХ ЗА СЕГОДНЯ")
    print("=" * 70)

    # Получаем API токен из конфигурации
    api_token = Config.API_TOKEN

    if not api_token:
        print("❌ Ошибка: API_TOKEN не найден в конфигурации.")
        print("   Убедитесь, что в файле .env установлена переменная API_TOKEN")
        return

    print(f"✅ API токен получен (длина: {len(api_token)} символов)")

    # Получаем сегодняшнюю дату
    today = get_today_date()
    start_date = today
    end_date = today

    print(f"\n📅 Сегодняшняя дата: {today}")
    print(f"🕐 Текущее время: {datetime.now().strftime('%H:%M:%S')}")
    print("-" * 70)

    # Получаем данные через API
    print(f"🚀 Начинаю загрузку данных за сегодня ({today})...")
    all_products = fetch_sales_funnel_data_today(api_token, start_date, end_date)

    if all_products:
        # Генерируем имя файла
        current_time = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"data/today/wb_sales_today_{current_time}.json"

        # Сохраняем данные в файл
        save_success = save_data_to_file(all_products, filename)

        if save_success:
            # Выводим отчет
            print_daily_report(all_products, filename)

            # Дополнительная информация
            print(f"\n💡 ИНФОРМАЦИЯ:")
            print(f"   1. Данные загружены с {start_date} 00:00 по текущее время")
            print(f"   2. Файл сохранен: {filename}")
            print(f"   3. Для повторной выгрузки запустите скрипт снова")
            print(f"   4. Данные обновляются в реальном времени")

    else:
        print("\n⚠️  Внимание: Не удалось получить данные за сегодня.")
        print("   Возможные причины:")
        print("   1. Еще нет данных за сегодня (раннее утро)")
        print("   2. Ошибка API (проверьте токен)")
        print("   3. Нет активных товаров в каталоге")

        # Все равно создаем пустой файл для отметки
        current_time = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"data/today/wb_sales_today_{current_time}_EMPTY.json"

        empty_data = {
            "metadata": {
                "export_date": datetime.now().isoformat(),
                "data_period": {"start": today, "end": today},
                "total_items": 0,
                "message": "Нет данных за сегодня",
                "status": "empty"
            },
            "products": []
        }

        try:
            os.makedirs("data/today", exist_ok=True)
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(empty_data, f, indent=2, ensure_ascii=False)
            print(f"💾 Создан пустой файл: {filename}")
        except Exception as e:
            print(f"❌ Ошибка при создании файла: {e}")

    print("\n" + "=" * 70)
    print("🎉 СКРИПТ ВЫПОЛНЕН УСПЕШНО!")
    print("=" * 70)


if __name__ == "__main__":
    # Создаем необходимые директории
    os.makedirs("data/today", exist_ok=True)

    # Запускаем основной скрипт
    main()