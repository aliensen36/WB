# storage/yesterday_statistics_storage.py
"""
Общее хранилище данных для статистики за вчера.
Используется и для ручных запросов, и для автоотчетов.
"""

user_data_store = {}  # Для ручных запросов
auto_report_data = {}  # Для автоотчетов


def get_user_data(user_id: int, is_auto_report: bool = False) -> dict:
    """Получить данные пользователя"""
    if is_auto_report:
        return auto_report_data.get(user_id, {})
    else:
        return user_data_store.get(user_id, {})


def set_user_data(user_id: int, data: dict, is_auto_report: bool = False):
    """Установить данные пользователя"""
    if is_auto_report:
        auto_report_data[user_id] = data
    else:
        user_data_store[user_id] = data


def delete_user_data(user_id: int, is_auto_report: bool = False):
    """Удалить данные пользователя"""
    if is_auto_report:
        auto_report_data.pop(user_id, None)
    else:
        user_data_store.pop(user_id, None)
