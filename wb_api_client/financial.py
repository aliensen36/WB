import requests
import json
from datetime import datetime, timedelta
from typing import List, Dict, Any
import time
from config import config


class WBReportDownloader:
    def __init__(self):
        self.base_url = "https://statistics-api.wildberries.ru"
        self.headers = {
            "Authorization": f"Bearer {config.API_TOKEN}",
            "Content-Type": "application/json"
        }
        self.report_data = []

    def test_connection(self):
        """Тестирует подключение к API"""
        test_url = f"{self.base_url}/api/v1/supplier/stocks"
        try:
            response = requests.get(test_url, headers=self.headers, params={"dateFrom": "2024-01-01"})
            print(f"Тест подключения: статус {response.status_code}")
            print(f"Заголовки ответа: {response.headers}")

            if response.status_code == 200:
                data = response.json()
                print(f"Тестовый ответ содержит {len(data) if isinstance(data, list) else 'не список'} элементов")
                return True
            elif response.status_code == 401:
                print("❌ Ошибка 401: Неавторизован. Проверьте токен.")
                print("Убедитесь, что используете токен для категории 'Статистика'")
                return False
            else:
                print(f"❌ Ошибка {response.status_code}: {response.text[:200]}")
                return False
        except Exception as e:
            print(f"❌ Ошибка подключения: {e}")
            return False

    def get_sales_report(self, date_from: str, date_to: str, period: str = "daily") -> List[Dict[str, Any]]:
        """
        Получает отчет о продажах по реализации
        """
        endpoint = "/api/v5/supplier/reportDetailByPeriod"
        url = self.base_url + endpoint

        print(f"\n📊 Запрос к {endpoint}")
        print(f"📅 Период: {date_from} - {date_to}")
        print(f"🔄 Периодичность: {period}")
        print(f"🔑 Используемый токен: {config.API_TOKEN[:10]}...{config.API_TOKEN[-10:]}")

        all_data = []
        rrdid = 0
        limit = 1000  # Начнем с малого лимита для теста

        try:
            while True:
                params = {
                    "dateFrom": date_from,
                    "dateTo": date_to,
                    "limit": limit,
                    "rrdid": rrdid,
                    "period": period
                }

                print(f"\n📨 Отправка запроса с параметрами:")
                print(f"   rrdid: {rrdid}, limit: {limit}")

                response = requests.get(url, headers=self.headers, params=params)

                print(f"📥 Ответ: статус {response.status_code}")
                print(f"📏 Размер ответа: {len(response.content)} байт")

                if response.status_code != 200:
                    print(f"❌ Ошибка API: {response.status_code}")
                    print(f"📄 Текст ответа: {response.text[:500]}")
                    break

                try:
                    data = response.json()
                except json.JSONDecodeError:
                    print(f"❌ Неверный JSON в ответе: {response.text[:200]}")
                    break

                print(f"📊 Получено элементов: {len(data) if isinstance(data, list) else 'не список'}")

                if not isinstance(data, list):
                    print(f"⚠️ Ответ не является списком: {type(data)}")
                    print(f"Содержимое: {data}")
                    break

                if not data:
                    print("✅ Получены все данные (пустой ответ)")
                    break

                all_data.extend(data)
                print(f"📈 Всего собрано: {len(all_data)} записей")

                # Если получено меньше limit, значит все данные получены
                if len(data) < limit:
                    print(f"✅ Получены все данные (меньше лимита)")
                    break

                # Получаем последний rrdid для следующего запроса
                last_rrdid = data[-1].get('rrd_id', 0)
                if last_rrdid == rrdid:
                    print("⚠️ rrd_id не изменился, завершаем")
                    break

                rrdid = last_rrdid

                # Соблюдаем лимиты
                time.sleep(61)

                # Для отладки ограничим количество запросов
                if len(all_data) >= 5000:
                    print("⚠️ Ограничиваем сбор для отладки (5000 записей)")
                    break

        except Exception as e:
            print(f"❌ Исключение: {e}")
            import traceback
            traceback.print_exc()

        return all_data

    def get_historical_data(self):
        """Получает исторические данные для тестирования"""
        # Используем прошедшую дату, когда точно были данные
        today = datetime.now()

        # Вариант 1: Вчерашний день
        yesterday = today - timedelta(days=1)
        date_from = yesterday.strftime("%Y-%m-%d")
        date_to = yesterday.strftime("%Y-%m-%d")

        print(f"\n🔍 Тест 1: Загружаем данные за вчера ({date_from})")
        data = self.get_sales_report(date_from, date_to, "daily")

        if not data:
            # Вариант 2: Позавчера
            day_before_yesterday = today - timedelta(days=2)
            date_from = day_before_yesterday.strftime("%Y-%m-%d")
            date_to = day_before_yesterday.strftime("%Y-%m-%d")

            print(f"\n🔍 Тест 2: Загружаем данные за позавчера ({date_from})")
            data = self.get_sales_report(date_from, date_to, "daily")

        if not data:
            # Вариант 3: Неделю назад
            week_ago = today - timedelta(days=7)
            date_from = week_ago.strftime("%Y-%m-%d")
            date_to = (week_ago + timedelta(days=2)).strftime("%Y-%m-%d")

            print(f"\n🔍 Тест 3: Загружаем данные за неделю назад ({date_from} - {date_to})")
            data = self.get_sales_report(date_from, date_to, "daily")

        return data

    def save_reports_to_file(self, filename: str = "wb_financial_reports.json"):
        """
        Сохраняет все отчеты в один JSON файл

        Args:
            filename: Имя файла для сохранения
        """
        if not self.report_data:
            print("❌ Нет данных для сохранения")
            return

        # Создаем структуру для сохранения
        report_structure = {
            "generated_at": datetime.now().isoformat(),
            "reports": self.report_data
        }

        try:
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(report_structure, f, ensure_ascii=False, indent=2)
            print(f"✅ Отчеты успешно сохранены в файл: {filename}")
            print(f"📊 Всего сохранено {len(self.report_data)} отчетов")
        except Exception as e:
            print(f"❌ Ошибка при сохранении файла: {e}")

    def add_report(self, endpoint_name: str, date_from: str, date_to: str,
                   data: List[Dict[str, Any]], description: str = ""):
        """
        Добавляет отчет в хранилище с метаданными

        Args:
            endpoint_name: Название эндпойнта
            date_from: Дата начала периода
            date_to: Дата окончания периода
            data: Данные отчета
            description: Описание отчета (опционально)
        """
        report = {
            "endpoint": endpoint_name,
            "date_from": date_from,
            "date_to": date_to,
            "retrieved_at": datetime.now().isoformat(),
            "description": description,
            "data": data,
            "records_count": len(data)
        }

        self.report_data.append(report)
        print(f"✅ Добавлен отчет '{endpoint_name}' с {len(data)} записями")

    def run_diagnostic(self):
        """Запускает диагностику"""
        print("=" * 60)
        print("🔧 ДИАГНОСТИКА ПОДКЛЮЧЕНИЯ К WB API")
        print("=" * 60)

        # 1. Тест подключения
        print("\n1. Тестируем подключение...")
        if not self.test_connection():
            print("❌ Проблема с подключением или токеном")
            return False

        # 2. Проверяем токен
        print("\n2. Проверяем токен...")
        print(f"Длина токена: {len(config.API_TOKEN)} символов")

        # 3. Пробуем получить исторические данные
        print("\n3. Пробуем получить исторические данные...")
        data = self.get_historical_data()

        if data:
            print(f"\n✅ УСПЕХ! Получено {len(data)} записей")

            # Показываем пример данных
            if len(data) > 0:
                print("\n📋 Пример первой записи:")
                print(json.dumps(data[0], indent=2, ensure_ascii=False)[:500])

                # Сохраняем в файл для анализа
                with open("debug_sample.json", "w", encoding="utf-8") as f:
                    json.dump(data[:10], f, indent=2, ensure_ascii=False)
                print(f"\n💾 Примеры данных сохранены в debug_sample.json")

            return True
        else:
            print("\n❌ Не удалось получить данные")
            print("\nВозможные причины:")
            print("1. Неверный токен (нужен токен категории 'Статистика')")
            print("2. Нет продаж за указанный период")
            print("3. Проблема с API Wildberries")
            print("4. Аккаунт не имеет доступа к отчетам")
            return False

    def get_last_week_report(self):
        """Получает отчет за последнюю неделю"""
        today = datetime.now()
        week_ago = today - timedelta(days=7)

        date_from = week_ago.strftime("%Y-%m-%d")
        date_to = (today - timedelta(days=1)).strftime("%Y-%m-%d")  # Не включаем сегодня

        print(f"\nЗагружаем отчет за период: {date_from} - {date_to}")

        try:
            data = self.get_sales_report(date_from, date_to, period="daily")
            self.add_report(
                endpoint_name="/api/v5/supplier/reportDetailByPeriod",
                date_from=date_from,
                date_to=date_to,
                data=data,
                description="Отчет о продажах по реализации (ежедневный)"
            )
            return data
        except Exception as e:
            print(f"❌ Ошибка при получении отчета: {e}")
            return []

    def get_custom_period_report(self, start_date: str, end_date: str, period: str = "daily"):
        """
        Получает отчет за произвольный период

        Args:
            start_date: Дата начала в формате YYYY-MM-DD
            end_date: Дата окончания в формате YYYY-MM-DD
            period: Периодичность отчета
        """
        print(f"\nЗагружаем отчет за период: {start_date} - {end_date}")

        try:
            data = self.get_sales_report(start_date, end_date, period)
            self.add_report(
                endpoint_name="/api/v5/supplier/reportDetailByPeriod",
                date_from=start_date,
                date_to=end_date,
                data=data,
                description=f"Отчет о продажах по реализации ({period})"
            )
            return data
        except Exception as e:
            print(f"❌ Ошибка при получении отчета: {e}")
            return []

    def run_complete_report(self):
        """Запускает полный процесс получения и сохранения отчетов"""
        print("=" * 50)
        print("Начало получения финансовых отчетов Wildberries")
        print("=" * 50)

        # Сначала проверяем подключение
        if not self.run_diagnostic():
            return

        # Пример: Получить отчет за последнюю неделю
        self.get_last_week_report()

        # Пример получения нескольких отчетов
        # today = datetime.now()
        # self.get_custom_period_report(
        #     start_date=(today - timedelta(days=14)).strftime("%Y-%m-%d"),
        #     end_date=(today - timedelta(days=8)).strftime("%Y-%m-%d"),
        #     period="daily"
        # )

        # Сохраняем все отчеты в один файл
        if self.report_data:
            self.save_reports_to_file("wb_financial_reports.json")

            # Дополнительно: вывод сводной информации
            print("\n" + "=" * 50)
            print("📊 Сводная информация по отчетам:")
            print("=" * 50)
            for i, report in enumerate(self.report_data, 1):
                print(f"\nОтчет #{i}:")
                print(f"  Эндпойнт: {report['endpoint']}")
                print(f"  Период: {report['date_from']} - {report['date_to']}")
                print(f"  Количество записей: {report['records_count']}")
                print(f"  Получено: {report['retrieved_at']}")
                if report['description']:
                    print(f"  Описание: {report['description']}")
        else:
            print("⚠️ Не удалось получить данные для отчетов")


def main():
    """
    Основная функция для запуска скачивания отчетов

    Пример использования:
    1. Создайте файл config.py с переменной API_TOKEN = 'ваш_токен'
    2. Запустите этот скрипт
    3. Отчеты сохранятся в файл wb_financial_reports.json
    """
    try:
        # Проверяем наличие токена
        if not hasattr(config, 'API_TOKEN') or not config.API_TOKEN:
            print("❌ Ошибка: Токен API не найден в config.py")
            print("Создайте файл config.py с содержимым:")
            print("API_TOKEN = 'ваш_токен_доступа'")
            return

        downloader = WBReportDownloader()
        downloader.run_complete_report()

    except ImportError:
        print("❌ Ошибка: Создайте файл config.py в той же папке с содержимым:")
        print("API_TOKEN = 'ваш_токен_доступа'")
    except Exception as e:
        print(f"❌ Неожиданная ошибка: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()