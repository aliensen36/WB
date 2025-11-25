import requests
import json
import time
from datetime import datetime, timedelta
import pandas as pd
from typing import List, Dict, Optional, Any

from config import config


class WBReports:
    def __init__(self, api_key: str):
        self.base_url = "https://statistics-api.wildberries.ru"
        self.headers = {
            "Authorization": f"Bearer {config.API_TOKEN}",
            "Content-Type": "application/json"
        }
        self.session = requests.Session()
        self.session.headers.update(self.headers)

    def _make_request(self, endpoint: str, params: Dict = None, method: str = "GET",
                      data: Dict = None) -> Optional[Any]:
        """Базовый метод для выполнения запросов"""
        url = f"{self.base_url}{endpoint}"

        try:
            if method == "GET":
                response = self.session.get(url, params=params)
            elif method == "POST":
                response = self.session.post(url, params=params, json=data)
            else:
                raise ValueError(f"Unsupported method: {method}")

            response.raise_for_status()
            return response.json()

        except requests.exceptions.RequestException as e:
            print(f"Ошибка запроса: {e}")
            if hasattr(e, 'response') and e.response is not None:
                print(f"Статус код: {e.response.status_code}")
                print(f"Текст ответа: {e.response.text}")
            return None

    def get_incomes(self, date_from: str) -> List[Dict]:
        """Получить данные о поставках"""
        all_incomes = []
        current_date_from = date_from

        while True:
            params = {"dateFrom": current_date_from}
            data = self._make_request("/api/v1/supplier/incomes", params)

            if not data or data == []:
                break

            all_incomes.extend(data)

            # Получаем последнюю дату для следующего запроса
            last_date = data[-1]["lastChangeDate"]
            current_date_from = last_date

            # Задержка для соблюдения лимитов
            time.sleep(60)

        return all_incomes

    def get_stocks(self, date_from: str) -> List[Dict]:
        """Получить данные об остатках"""
        all_stocks = []
        current_date_from = date_from

        while True:
            params = {"dateFrom": current_date_from}
            data = self._make_request("/api/v1/supplier/stocks", params)

            if not data or data == []:
                break

            all_stocks.extend(data)

            # Получаем последнюю дату для следующего запроса
            last_date = data[-1]["lastChangeDate"]
            current_date_from = last_date

            time.sleep(60)

        return all_stocks

    def get_orders(self, date_from: str, flag: int = 0) -> List[Dict]:
        """Получить данные о заказах"""
        all_orders = []
        current_date_from = date_from

        while True:
            params = {
                "dateFrom": current_date_from,
                "flag": flag
            }
            data = self._make_request("/api/v1/supplier/orders", params)

            if not data or data == []:
                break

            all_orders.extend(data)

            # Получаем последнюю дату для следующего запроса
            last_date = data[-1]["lastChangeDate"]
            current_date_from = last_date

            time.sleep(60)

        return all_orders

    def get_sales(self, date_from: str, flag: int = 0) -> List[Dict]:
        """Получить данные о продажах"""
        all_sales = []
        current_date_from = date_from

        while True:
            params = {
                "dateFrom": current_date_from,
                "flag": flag
            }
            data = self._make_request("/api/v1/supplier/sales", params)

            if not data or data == []:
                break

            all_sales.extend(data)

            # Получаем последнюю дату для следующего запроса
            last_date = data[-1]["lastChangeDate"]
            current_date_from = last_date

            time.sleep(60)

        return all_sales

    def get_warehouse_remains_report(self, group_by_nm: bool = True,
                                     group_by_brand: bool = False) -> Optional[Dict]:
        """Создать отчет об остатках на складах"""
        params = {
            "groupByNm": group_by_nm,
            "groupByBrand": group_by_brand,
            "locale": "ru"
        }

        response = self._make_request("/api/v1/warehouse_remains", params)
        return response

    def check_task_status(self, task_id: str, report_type: str = "warehouse_remains") -> Optional[Dict]:
        """Проверить статус задания"""
        if report_type == "warehouse_remains":
            endpoint = f"/api/v1/warehouse_remains/tasks/{task_id}/status"
        elif report_type == "acceptance_report":
            endpoint = f"/api/v1/acceptance_report/tasks/{task_id}/status"
        elif report_type == "paid_storage":
            endpoint = f"/api/v1/paid_storage/tasks/{task_id}/status"
        else:
            raise ValueError("Unknown report type")

        return self._make_request(endpoint)

    def download_report(self, task_id: str, report_type: str = "warehouse_remains") -> Optional[Dict]:
        """Скачать готовый отчет"""
        if report_type == "warehouse_remains":
            endpoint = f"/api/v1/warehouse_remains/tasks/{task_id}/download"
        elif report_type == "acceptance_report":
            endpoint = f"/api/v1/acceptance_report/tasks/{task_id}/download"
        elif report_type == "paid_storage":
            endpoint = f"/api/v1/paid_storage/tasks/{task_id}/download"
        else:
            raise ValueError("Unknown report type")

        return self._make_request(endpoint)

    def wait_for_report_completion(self, task_id: str, report_type: str,
                                   max_wait_time: int = 300) -> bool:
        """Ожидать завершения генерации отчета"""
        start_time = time.time()

        while time.time() - start_time < max_wait_time:
            status_response = self.check_task_status(task_id, report_type)

            if status_response and status_response.get("data", {}).get("status") == "done":
                return True
            elif status_response and status_response.get("data", {}).get("status") == "error":
                print(f"Ошибка генерации отчета: {status_response}")
                return False

            time.sleep(5)

        print("Превышено время ожидания генерации отчета")
        return False

    def get_excise_report(self, date_from: str, date_to: str,
                          countries: List[str] = ["RU"]) -> Optional[Dict]:
        """Получить отчет по товарам с обязательной маркировкой"""
        params = {
            "dateFrom": date_from,
            "dateTo": date_to
        }
        data = {
            "countries": countries
        }

        return self._make_request("/api/v1/analytics/excise-report", params, "POST", data)

    def get_warehouse_measurements(self, date_from: str, date_to: str,
                                   tab: str, limit: int, offset: int = 0) -> Optional[Dict]:
        """Получить отчет об удержаниях за занижение габаритов"""
        params = {
            "dateFrom": date_from,
            "dateTo": date_to,
            "tab": tab,
            "limit": limit,
            "offset": offset
        }

        return self._make_request("/api/v1/analytics/warehouse-measurements", params)

    def get_antifraud_details(self, date: str = None) -> Optional[Dict]:
        """Получить отчет о самовыкупах"""
        params = {}
        if date:
            params["date"] = date

        return self._make_request("/api/v1/analytics/antifraud-details", params)

    def get_incorrect_attachments(self, date_from: str, date_to: str) -> Optional[Dict]:
        """Получить отчет о подмене товара"""
        params = {
            "dateFrom": date_from,
            "dateTo": date_to
        }

        return self._make_request("/api/v1/analytics/incorrect-attachments", params)

    def get_goods_labeling(self, date_from: str, date_to: str) -> Optional[Dict]:
        """Получить отчет о маркировке товара"""
        params = {
            "dateFrom": date_from,
            "dateTo": date_to
        }

        return self._make_request("/api/v1/analytics/goods-labeling", params)

    def get_characteristics_change(self, date_from: str, date_to: str) -> Optional[Dict]:
        """Получить отчет о смене характеристик"""
        params = {
            "dateFrom": date_from,
            "dateTo": date_to
        }

        return self._make_request("/api/v1/analytics/characteristics-change", params)

    def create_acceptance_report(self, date_from: str, date_to: str) -> Optional[Dict]:
        """Создать отчет о платной приемке"""
        params = {
            "dateFrom": date_from,
            "dateTo": date_to
        }

        return self._make_request("/api/v1/acceptance_report", params)

    def create_paid_storage_report(self, date_from: str, date_to: str) -> Optional[Dict]:
        """Создать отчет о платном хранении"""
        params = {
            "dateFrom": date_from,
            "dateTo": date_to
        }

        return self._make_request("/api/v1/paid_storage", params)

    def get_region_sale(self, date_from: str, date_to: str) -> Optional[Dict]:
        """Получить отчет о продажах по регионам"""
        params = {
            "dateFrom": date_from,
            "dateTo": date_to
        }

        return self._make_request("/api/v1/analytics/region-sale", params)

    def get_brand_share_brands(self) -> Optional[Dict]:
        """Получить список брендов продавца"""
        return self._make_request("/api/v1/analytics/brand-share/brands")

    def get_brand_share_parent_subjects(self, brand: str, date_from: str,
                                        date_to: str, locale: str = "ru") -> Optional[Dict]:
        """Получить родительские категории бренда"""
        params = {
            "brand": brand,
            "dateFrom": date_from,
            "dateTo": date_to,
            "locale": locale
        }

        return self._make_request("/api/v1/analytics/brand-share/parent-subjects", params)

    def get_brand_share(self, parent_id: int, brand: str, date_from: str,
                        date_to: str) -> Optional[Dict]:
        """Получить отчет о доле бренда в продажах"""
        params = {
            "parentId": parent_id,
            "brand": brand,
            "dateFrom": date_from,
            "dateTo": date_to
        }

        return self._make_request("/api/v1/analytics/brand-share", params)

    def get_banned_products_blocked(self, sort: str, order: str) -> Optional[Dict]:
        """Получить заблокированные карточки"""
        params = {
            "sort": sort,
            "order": order
        }

        return self._make_request("/api/v1/analytics/banned-products/blocked", params)

    def get_banned_products_shadowed(self, sort: str, order: str) -> Optional[Dict]:
        """Получить скрытые из каталога товары"""
        params = {
            "sort": sort,
            "order": order
        }

        return self._make_request("/api/v1/analytics/banned-products/shadowed", params)

    def get_goods_return(self, date_from: str, date_to: str) -> Optional[Dict]:
        """Получить отчет о возвратах"""
        params = {
            "dateFrom": date_from,
            "dateTo": date_to
        }

        return self._make_request("/api/v1/analytics/goods-return", params)

    def save_to_excel(self, data: List[Dict], filename: str):
        """Сохранить данные в Excel файл"""
        if data:
            df = pd.DataFrame(data)
            df.to_excel(filename, index=False)
            print(f"Данные сохранены в файл: {filename}")
        else:
            print("Нет данных для сохранения")

    def save_to_json(self, data: List[Dict], filename: str):
        """Сохранить данные в JSON файл"""
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(f"Данные сохранены в файл: {filename}")


# Пример использования
def main():
    # Инициализация с вашим API ключом
    api_key = "YOUR_API_KEY_HERE"
    wb = WBReports(api_key)

    # Установите начальную дату (можно использовать старую дату для получения всех данных)
    date_from = "2023-01-01"
    current_date = datetime.now().strftime("%Y-%m-%d")

    try:
        # 1. Основные отчеты
        print("Получение данных о поставках...")
        incomes = wb.get_incomes(date_from)
        if incomes:
            wb.save_to_excel(incomes, "incomes.xlsx")

        print("Получение данных об остатках...")
        stocks = wb.get_stocks(date_from)
        if stocks:
            wb.save_to_excel(stocks, "stocks.xlsx")

        print("Получение данных о заказах...")
        orders = wb.get_orders(date_from)
        if orders:
            wb.save_to_excel(orders, "orders.xlsx")

        print("Получение данных о продажах...")
        sales = wb.get_sales(date_from)
        if sales:
            wb.save_to_excel(sales, "sales.xlsx")

        # 2. Отчет об остатках на складах (асинхронный)
        print("Создание отчета об остатках на складах...")
        remains_task = wb.get_warehouse_remains_report()
        if remains_task and remains_task.get("data", {}).get("taskId"):
            task_id = remains_task["data"]["taskId"]
            if wb.wait_for_report_completion(task_id, "warehouse_remains"):
                remains_data = wb.download_report(task_id, "warehouse_remains")
                if remains_data:
                    wb.save_to_json(remains_data, "warehouse_remains.json")

        # 3. Отчеты об удержаниях
        print("Получение отчета о самовыкупах...")
        antifraud = wb.get_antifraud_details()
        if antifraud:
            wb.save_to_json(antifraud, "antifraud.json")

        # 4. Отчет о продажах по регионам
        print("Получение отчета о продажах по регионам...")
        region_sales = wb.get_region_sale(date_from, current_date)
        if region_sales:
            wb.save_to_json(region_sales, "region_sales.json")

        # 5. Скрытые товары
        print("Получение списка заблокированных товаров...")
        blocked = wb.get_banned_products_blocked("nmId", "desc")
        if blocked:
            wb.save_to_json(blocked, "blocked_products.json")

        print("Все отчеты успешно выгружены!")

    except Exception as e:
        print(f"Произошла ошибка: {e}")


if __name__ == "__main__":
    main()