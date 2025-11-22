utils.py
import json
from datetime import datetime, timedelta


def save_to_json(data: Dict, filename: str):
    """Сохранение данных в JSON файл"""
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def load_from_json(filename: str) -> Dict:
    """Загрузка данных из JSON файла"""
    with open(filename, 'r', encoding='utf-8') as f:
        return json.load(f)


def get_date_rfc3339(days_back: int = 7) -> str:
    """Получение даты в формате RFC3339"""
    target_date = datetime.now() - timedelta(days=days_back)
    return target_date.isoformat() + 'Z'


# Пример использования утилит
def export_orders_to_file(wb_api: WildberriesAPI, days: int = 30):
    """Экспорт заказов в файл"""
    date_from = get_date_rfc3339(days)
    orders = wb_api.get_orders(date_from=date_from)

    filename = f"orders_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    save_to_json(orders, filename)
    print(f"Заказы сохранены в файл: {filename}")
