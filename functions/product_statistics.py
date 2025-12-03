# # functions/product_statistics.py
# from collections import defaultdict
# from datetime import datetime, timedelta
# from typing import Dict, List, Tuple
# import logging
# from database.product_manager import ProductManager
#
# logger = logging.getLogger(__name__)
#
#
# class ProductStatisticsService:
#     def __init__(self, product_manager: ProductManager):
#         self.product_manager = product_manager
#
#     def get_yesterday_info(self) -> Dict[str, str]:
#         """Получить информацию о вчерашнем дне"""
#         yesterday = datetime.now().date() - timedelta(days=1)
#         days = ["Понедельник", "Вторник", "Среда", "Четверг", "Пятница", "Суббота", "Воскресенье"]
#
#         return {
#             'date_str': yesterday.strftime("%d.%m.%Y"),
#             'day_name': days[yesterday.weekday()]
#         }
#
#     async def process_orders_data_only(
#             self,
#             seller_account_id: int,
#             orders_data: List[Dict]
#     ) -> Tuple[Dict, Dict]:
#         """
#         Обрабатываем данные ТОЛЬКО из API заказов (/api/v1/supplier/orders)
#         Используем isRealization для определения выкупов
#         """
#         product_stats = defaultdict(lambda: {
#             'orders_amount': 0.0,  # Сумма всех неотмененных заказов
#             'orders_qty': 0,  # Количество всех неотмененных заказов
#             'sales_amount': 0.0,  # Сумма выкупленных заказов (isRealization = true)
#             'sales_qty': 0,  # Количество выкупленных заказов (isRealization = true)
#             'cancelled_qty': 0,  # Количество отмененных заказов
#             'realization_false_qty': 0  # Количество невыкупленных заказов
#         })
#
#         # Инициализируем product_info с ВСЕМИ необходимыми ключами
#         product_info = {
#             'created': 0,
#             'unique_articles': set(),
#             'total_records': len(orders_data),
#             'records_processed': 0,  # ДОБАВЛЕНО: счетчик обработанных записей
#             'realization_true': 0,  # Выкупленные
#             'realization_false': 0,  # Невыкупленные
#             'cancelled': 0,  # Отмененные
#             'not_cancelled': 0  # Неотмененные
#         }
#
#         # Обработка всех записей из API заказов
#         for order in orders_data:
#             supplier_article = order.get('supplierArticle')
#             if not supplier_article:
#                 continue
#
#             product_info['records_processed'] += 1
#
#             # Создаем/получаем товар
#             if supplier_article not in product_info['unique_articles']:
#                 product = await self.product_manager.get_or_create_product(
#                     seller_account_id=seller_account_id,
#                     supplier_article=supplier_article
#                 )
#                 if product:
#                     product_info['created'] += 1
#                     product_info['unique_articles'].add(supplier_article)
#             else:
#                 # Получаем существующий товар для обновления статистики
#                 await self.product_manager.get_or_create_product(
#                     seller_account_id=seller_account_id,
#                     supplier_article=supplier_article
#                 )
#
#             # Получаем ключевые поля из заказа
#             is_cancel = order.get('isCancel', False)
#             is_realization = order.get('isRealization', True)
#             price = float(order.get('priceWithDisc', 0))
#
#             # Обработка quantity (может быть None, поэтому нужна проверка)
#             quantity_raw = order.get('quantity')
#             if quantity_raw is None:
#                 logger.debug(f"Товар {supplier_article}: quantity=None, используем 1")
#                 quantity = 1
#             else:
#                 try:
#                     quantity = int(quantity_raw)
#                 except (ValueError, TypeError):
#                     logger.warning(f"Товар {supplier_article}: quantity={quantity_raw} не int, используем 1")
#                     quantity = 1
#
#             # Статистика по статусам
#             if is_cancel:
#                 product_info['cancelled'] += 1
#                 product_stats[supplier_article]['cancelled_qty'] += quantity
#             else:
#                 product_info['not_cancelled'] += 1
#
#                 # Все неотмененные заказы
#                 product_stats[supplier_article]['orders_qty'] += quantity
#                 product_stats[supplier_article]['orders_amount'] += price * quantity
#
#                 # Разделяем на выкупленные и невыкупленные
#                 if is_realization:
#                     product_info['realization_true'] += 1
#                     product_stats[supplier_article]['sales_qty'] += quantity
#                     product_stats[supplier_article]['sales_amount'] += price * quantity
#                 else:
#                     product_info['realization_false'] += 1
#                     product_stats[supplier_article]['realization_false_qty'] += quantity
#
#         # Вычисляем итоги для каждого товара
#         for article in product_stats:
#             stats = product_stats[article]
#             stats['total_amount'] = stats['sales_amount']  # Только выкупленные
#             stats['total_qty'] = stats['sales_qty']  # Только выкупленные
#
#             # Логируем статистику для отладки
#             if stats['sales_qty'] > 0:
#                 logger.info(f"Товар {article}: {stats['sales_qty']} выкупов, сумма {stats['sales_amount']:.2f}₽")
#
#         product_info['existing'] = len(product_info['unique_articles']) - product_info['created']
#
#         # Логирование итогов
#         logger.info(f"✅ Обработано записей: {product_info['records_processed']}/{product_info['total_records']}")
#         logger.info(f"📊 Статистика: выкуплено={product_info['realization_true']}, "
#                     f"невыкуплено={product_info['realization_false']}, отменено={product_info['cancelled']}")
#
#         return dict(product_stats), product_info
#
#     async def generate_product_report(
#             self,
#             seller_account_id: int,
#             product_stats: Dict
#     ) -> List[Dict]:
#         """
#         Генерируем отчет по товарам с кастомными названиями
#         """
#         # Получаем кастомные названия
#         custom_names = await self.product_manager.get_custom_names_dict(seller_account_id)
#
#         report = []
#
#         for article, stats in product_stats.items():
#             # Используем кастомное название или артикул
#             display_name = custom_names.get(article, article)
#
#             # Пропускаем товары без выкупов
#             if stats['sales_qty'] == 0 and stats['sales_amount'] == 0:
#                 continue
#
#             report_item = {
#                 'supplier_article': article,
#                 'display_name': display_name,
#                 'orders_amount': round(stats['orders_amount'], 2),
#                 'orders_qty': stats['orders_qty'],
#                 'sales_amount': round(stats['sales_amount'], 2),
#                 'sales_qty': stats['sales_qty'],
#                 'total_amount': round(stats['total_amount'], 2),
#                 'total_qty': stats['total_qty']
#             }
#
#             report.append(report_item)
#
#         # Сортируем по сумме выкупов (от большего к меньшему)
#         return sorted(report, key=lambda x: x['sales_amount'], reverse=True)
