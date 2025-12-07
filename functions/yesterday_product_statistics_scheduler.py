# functions/yesterday_product_statistics_scheduler.py
import asyncio
import logging
from datetime import datetime, timedelta
import pytz
from aiogram import Bot
from aiogram.types import ChatMemberAdministrator, ChatMemberOwner
from database.account_manager import AccountManager
from database.product_manager import ProductManager
from functions.yesterday_product_statistics import YesterdayProductStatistics

logger = logging.getLogger(__name__)


class YesterdayProductStatisticsScheduler:
    def __init__(self, bot: Bot, session_maker, admin_chat_id: int):
        self.bot = bot
        self.session_maker = session_maker
        self.admin_chat_id = admin_chat_id
        # Устанавливаем московскую временную зону
        self.moscow_tz = pytz.timezone('Europe/Moscow')

    async def get_admin_users_from_chat(self):
        """Получить список администраторов и владельца группы"""
        admin_users = []

        try:
            # Получаем список администраторов чата
            chat_admins = await self.bot.get_chat_administrators(self.admin_chat_id)

            for admin in chat_admins:
                # Проверяем, что пользователь является администратором или владельцем
                if isinstance(admin, (ChatMemberAdministrator, ChatMemberOwner)):
                    # Проверяем, что у пользователя есть username или можно отправить сообщение
                    if admin.user.is_bot:
                        continue  # Пропускаем ботов

                    admin_users.append(admin.user)
                    logger.info(f"Найден администратор для автоотчета: {admin.user.first_name} (ID: {admin.user.id})")

            logger.info(f"Всего найдено администраторов для автоотчета: {len(admin_users)}")

        except Exception as e:
            logger.error(f"Ошибка при получении списка администраторов для автоотчета: {e}")

        return admin_users

    async def prepare_yesterday_auto_report(self, admin_id: int):
        """Подготовить и отправить автоотчет за вчера администратору"""
        try:
            logger.info(f"Начало подготовки автоотчета за вчера для пользователя {admin_id}")

            # Импортируем функции хранилища из storage
            from storage.yesterday_statistics_storage import set_user_data, delete_user_data

            # Создаем структуру данных для пользователя
            user_data = {
                "account_index": 0,
                "store_index": 0,
                "current_page": {},
                "store_data": {},
                "stores_order": [],
                "total_accounts": 0,
                "date_str": "",
                "day_name": "",
                "successful_accounts": 0,
                "failed_accounts": 0,
                "header_message_id": None,
                "is_auto_report": True  # Флаг автоотчета
            }

            # Сохраняем данные пользователя
            set_user_data(admin_id, user_data, is_auto_report=True)

            # Отправляем заголовок статистики
            header_text = "⏳ <b>Подготовка автоматического отчета за вчерашний день (07:00)...</b>"
            header_msg = await self.bot.send_message(admin_id, header_text)
            user_data["header_message_id"] = header_msg.message_id
            set_user_data(admin_id, user_data, is_auto_report=True)

            async with self.session_maker() as session:
                account_manager = AccountManager(session)
                all_accounts = await account_manager.get_all_accounts()

                if not all_accounts:
                    await self.bot.edit_message_text(
                        "❌ <b>Нет добавленных магазинов</b>\n\nДобавьте магазины в настройках.",
                        chat_id=admin_id,
                        message_id=header_msg.message_id
                    )
                    delete_user_data(admin_id, is_auto_report=True)
                    return

                # Получаем дату вчерашнего дня в московском времени
                moscow_time = datetime.now(self.moscow_tz)
                yesterday_date_obj = moscow_time - timedelta(days=1)
                date_str = yesterday_date_obj.strftime("%d.%m.%Y")
                days = ["Понедельник", "Вторник", "Среда", "Четверг", "Пятница", "Суббота", "Воскресенье"]
                day_name = days[yesterday_date_obj.weekday()]

                user_data["date_str"] = date_str
                user_data["day_name"] = day_name
                user_data["total_accounts"] = len(all_accounts)

                successful_accounts = 0
                failed_accounts = 0
                stores_order = []

                # Обрабатываем каждый магазин
                for account_index, account in enumerate(all_accounts, 1):
                    account_name = account.account_name or f"Магазин {account.id}"

                    # Обновляем сообщение о загрузке
                    try:
                        await self.bot.edit_message_text(
                            f"⏳ <b>Автоотчет за {date_str} (07:00)</b>\n"
                            f"Обработка магазина {account_index}/{len(all_accounts)}\n"
                            f"<i>{account_name}</i>",
                            chat_id=admin_id,
                            message_id=header_msg.message_id
                        )
                    except:
                        pass

                    try:
                        # Получаем комбинированную статистику
                        yesterday_stats = YesterdayProductStatistics(account.api_key)
                        combined_stats = await yesterday_stats.get_combined_yesterday_stats()

                        funnel_stats = combined_stats.get("funnel_stats", {})
                        sales_stats = combined_stats.get("sales_stats", {})
                        recommended_stats = combined_stats.get("recommended_stats", {})

                        # Получаем детальные данные по товарам
                        try:
                            stats_obj = YesterdayProductStatistics(account.api_key)
                            detailed_stats = await stats_obj.get_yesterday_product_stats()

                            # Сохраняем товары в БД
                            product_manager = ProductManager(session)
                            all_products_for_save = detailed_stats.get("all_products", [])

                            for product_data in all_products_for_save:
                                try:
                                    article = product_data.get('article')
                                    if article:
                                        product = await product_manager.get_or_create_product(
                                            seller_account_id=account.id,
                                            supplier_article=article
                                        )

                                        title = product_data.get('title')
                                        if title and not product.custom_name:
                                            short_title = title[:100] if len(title) > 100 else title
                                            await product_manager.update_custom_name(
                                                seller_account_id=account.id,
                                                supplier_article=article,
                                                custom_name=short_title
                                            )
                                except Exception as e:
                                    logger.error(f"Ошибка при сохранении товара: {e}")

                        except Exception as e:
                            logger.error(f"[{account_name}] Ошибка при получении детальных данных: {e}")
                            detailed_stats = {}

                        # Получаем кастомные названия из БД
                        product_manager = ProductManager(session)
                        custom_names = await product_manager.get_custom_names_dict(account.id)

                        # Получаем товары с активностью
                        products_with_activity = []
                        try:
                            products_with_orders = detailed_stats.get("products", [])
                            if not products_with_orders:
                                all_products = detailed_stats.get("all_products", [])
                                products_with_activity = [p for p in all_products if
                                                          p.get('orders', 0) > 0 or p.get('buyouts', 0) > 0]
                            else:
                                products_with_activity = [p for p in products_with_orders if
                                                          p.get('orders', 0) > 0 or p.get('buyouts', 0) > 0]

                            products_with_activity.sort(key=lambda x: x.get('orders', 0), reverse=True)

                        except Exception as e:
                            logger.error(f"[{account_name}] Ошибка при получении товаров с активностью: {e}")
                            products_with_activity = []

                        # Сохраняем данные магазина
                        store_data = {
                            "account_name": account_name,
                            "account_id": account.id,
                            "products_with_activity": products_with_activity,
                            "custom_names": custom_names,
                            "funnel_stats": funnel_stats,
                            "sales_stats": sales_stats,
                            "recommended_stats": recommended_stats,
                            "detailed_stats": detailed_stats,
                            "total_views": detailed_stats.get("total_views", 0) if detailed_stats else 0,
                            "total_carts": detailed_stats.get("total_carts", 0) if detailed_stats else 0,
                            "overall_cart_conversion": detailed_stats.get("overall_cart_conversion",
                                                                          0) if detailed_stats else 0,
                            "overall_order_conversion": detailed_stats.get("overall_order_conversion",
                                                                           0) if detailed_stats else 0,
                            "has_activity": len(products_with_activity) > 0
                        }

                        user_data["store_data"][account_name] = store_data
                        stores_order.append(account_name)

                        if funnel_stats.get("total_orders", 0) > 0 or recommended_stats.get("total_buyouts", 0) > 0:
                            successful_accounts += 1
                        else:
                            failed_accounts += 1

                    except Exception as e:
                        error_message = str(e)
                        logger.error(f"[{account_name}] Ошибка: {error_message}")
                        failed_accounts += 1

                        error_data = {
                            "account_name": account_name,
                            "error": True,
                            "error_message": error_message,
                            "display_error": "Неизвестная ошибка"
                        }

                        if "Неверный API ключ" in error_message:
                            error_data["display_error"] = "Неверный API ключ"
                        elif "Превышен лимит запросов" in error_message:
                            error_data["display_error"] = "Превышен лимит запросов API"
                        elif "Таймаут запроса" in error_message:
                            error_data["display_error"] = "Таймаут запроса"
                        else:
                            error_data["display_error"] = "Ошибка подключения к API"

                        user_data["store_data"][account_name] = error_data
                        stores_order.append(account_name)

                    # Обновляем данные пользователя после каждого магазина
                    set_user_data(admin_id, user_data, is_auto_report=True)

                    # Задержка между запросами
                    if account_index < len(all_accounts):
                        await asyncio.sleep(5)

                user_data["stores_order"] = stores_order
                user_data["successful_accounts"] = successful_accounts
                user_data["failed_accounts"] = failed_accounts
                set_user_data(admin_id, user_data, is_auto_report=True)

                # Обновляем заголовок
                header_text = (f"<b>📊 СТАТИСТИКА ЗА ВЧЕРА (07:00)</b>\n"
                               f"📅 {date_str} ({day_name})\n"
                               f"Всего магазинов: {len(all_accounts)}\n"
                               f"Успешно: {successful_accounts} | Ошибок: {failed_accounts}\n\n"
                               f"<i>Используйте кнопки для навигации</i>")

                await self.bot.edit_message_text(
                    header_text,
                    chat_id=admin_id,
                    message_id=header_msg.message_id
                )

                # Импортируем функции отображения из handlers
                from handlers.yesterday_product_statistics_handlers import (
                    show_store_summary, show_error_message
                )

                # Показываем первый магазин (итоги)
                if stores_order:
                    first_store = stores_order[0]
                    store_data = user_data["store_data"].get(first_store)

                    if store_data.get("error", False):
                        # Используем общую функцию show_error_message
                        await show_error_message(
                            message=None,  # Будем отправлять новое сообщение
                            user_id=admin_id,
                            store_name=first_store,
                            store_data=store_data,
                            edit_message=None,
                            is_auto_report=True,
                            bot=self.bot  # Добавляем передачу бота
                        )
                    else:
                        # Используем общую функцию show_store_summary
                        await show_store_summary(
                            message=None,
                            user_id=admin_id,
                            store_name=first_store,
                            store_data=store_data,
                            edit_message=None,
                            is_auto_report=True,
                            bot=self.bot  # Передаем бота явно
                        )
                else:
                    await self.bot.send_message(
                        admin_id,
                        "❌ Не удалось получить данные ни от одного магазина"
                    )

                logger.info(f"Автоотчет за вчера отправлен пользователю {admin_id}")

        except Exception as e:
            logger.error(f"Ошибка при подготовке автоотчета пользователю {admin_id}: {e}")
            try:
                # Очищаем данные при ошибке
                from storage.yesterday_statistics_storage import delete_user_data
                delete_user_data(admin_id, is_auto_report=True)

                await self.bot.send_message(
                    admin_id,
                    f"❌ <b>Ошибка при подготовке автоотчета</b>\n"
                    f"<i>{str(e)[:100]}</i>"
                )
            except:
                pass

    async def send_yesterday_auto_reports(self):
        """Отправить автоотчеты за вчера всем администраторам"""
        try:
            # Получаем список администраторов
            admin_users = await self.get_admin_users_from_chat()

            if not admin_users:
                logger.warning("Не найдено администраторов для отправки автоотчета за вчера")
                return

            successful_sends = 0
            failed_sends = 0

            # Отправляем каждому администратору в личный чат
            for admin in admin_users:
                try:
                    await self.prepare_yesterday_auto_report(admin.id)
                    logger.info(
                        f"Автоотчет за вчера (07:00) отправлен пользователю {admin.first_name} (ID: {admin.id})")
                    successful_sends += 1

                    # Задержка между отправками
                    await asyncio.sleep(1)

                except Exception as e:
                    logger.error(
                        f"Ошибка при отправке автоотчета за вчера пользователю {admin.first_name} (ID: {admin.id}): {e}")
                    failed_sends += 1

            logger.info(
                f"Итоги отправки автоотчетов за вчера (07:00): успешно {successful_sends}, ошибок {failed_sends}")

        except Exception as e:
            logger.error(f"Ошибка при подготовке автоотчетов за вчера (07:00): {e}")

    def get_moscow_time(self):
        """Получить текущее московское время"""
        return datetime.now(self.moscow_tz)

    async def start_scheduler(self):
        """Запустить планировщик отчетов за вчера"""
        logger.info("Планировщик автоотчетов за вчера запущен")
        logger.info(f"Отчеты будут приходить в личные чаты администраторов из группы (ID: {self.admin_chat_id})")
        logger.info(f"Используется временная зона: {self.moscow_tz}")

        # ВРЕМЕННО ДЛЯ ТЕСТИРОВАНИЯ - изменить на удобное время
        # Например, через 2 минуты от текущего времени
        test_time_add_minutes = 2
        now = self.get_moscow_time()
        test_time = now + timedelta(minutes=test_time_add_minutes)
        target_hour = test_time.hour
        target_minute = test_time.minute

        logger.warning(f"ТЕСТОВЫЙ РЕЖИМ! Автоотчет будет отправлен в {target_hour:02d}:{target_minute:02d} МСК")
        logger.warning(f"Текущее время: {now.strftime('%H:%M:%S')}, отчет через {test_time_add_minutes} минут")

        while True:
            # Используем московское время для проверки
            now = self.get_moscow_time()

            # Логируем текущее время для отладки
            logger.debug(f"Текущее московское время: {now.strftime('%H:%M:%S')}")

            # Проверяем время отправки автоотчета за вчера
            if now.hour == target_hour and now.minute == target_minute:
                scheduled_time = f"{target_hour:02d}:{target_minute:02d} МСК (ТЕСТ)"

                logger.info(f"Время автоотчета за вчера: {scheduled_time}")
                logger.info(f"Текущее серверное время UTC: {datetime.utcnow().strftime('%H:%M:%S')}")
                logger.info(f"Текущее московское время: {now.strftime('%H:%M:%S')}")

                try:
                    await self.send_yesterday_auto_reports()
                    logger.info(f"Автоотчет за вчера {scheduled_time} обработан")

                    # После теста меняем на рабочее время
                    logger.info("Тест завершен. Переключаюсь на рабочее время 07:00")
                    target_hour = 7
                    target_minute = 0

                except Exception as e:
                    logger.error(f"Ошибка при обработке автоотчета за вчера {scheduled_time}: {e}")

                # Ждем 61 секунду чтобы не отправить повторно
                await asyncio.sleep(61)

            # Ждем 30 секунд до следующей проверки
            await asyncio.sleep(30)

    async def send_test_report_now(self, admin_id: int = None):
        """Отправить тестовый отчет прямо сейчас (для отладки)"""
        logger.info("Запуск тестового отчета за вчера...")

        try:
            if admin_id:
                # Отправляем конкретному администратору
                await self.prepare_yesterday_auto_report(admin_id)
                logger.info(f"Тестовый отчет отправлен пользователю {admin_id}")
                return True
            else:
                # Отправляем всем администраторам
                await self.send_yesterday_auto_reports()
                logger.info("Тестовый отчет отправлен всем администраторам")
                return True

        except Exception as e:
            logger.error(f"Ошибка при отправке тестового отчета: {e}")
            return False
