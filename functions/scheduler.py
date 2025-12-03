# functions/scheduler.py
import asyncio
from aiogram import Bot
from aiogram.types import ChatMemberAdministrator, ChatMemberOwner
from database.account_manager import AccountManager
from datetime import datetime, timezone
import pytz
import logging

from functions.current_statistics import CurrentStatistics

logger = logging.getLogger(__name__)


class StatisticsScheduler:
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
                    logger.info(f"Найден администратор: {admin.user.first_name} (ID: {admin.user.id})")

            logger.info(f"Всего найдено администраторов: {len(admin_users)}")

        except Exception as e:
            logger.error(f"Ошибка при получении списка администраторов: {e}")

        return admin_users

    async def get_daily_stats_message(self, scheduled_time: str) -> str:
        """Сформировать сообщение со статистикой за сегодня для расписания"""
        async with self.session_maker() as session:
            account_manager = AccountManager(session)
            all_accounts = await account_manager.get_all_accounts()

            if not all_accounts:
                return "<b>Нет добавленных магазинов</b>\n\nДобавьте магазины в настройках."

            # Используем московское время для даты
            moscow_time = datetime.now(self.moscow_tz)
            today = moscow_time.strftime("%d.%m.%Y")

            # Добавляем заголовок для расписания
            stats_text = f"<b>Автоматический отчет ({scheduled_time})</b>\n\n"
            stats_text += f"<b>Статистика всех магазинов</b>\n\n"
            stats_text += f"За сегодня (<b>{today}</b>)\n\n"

            successful_accounts = 0
            rate_limited_accounts = 0

            # Собираем статистику по каждому магазину
            for i, account in enumerate(all_accounts):
                account_display_name = account.account_name or f"Магазин {account.id}"

                try:
                    # Задержка между запросами к разным аккаунтам (2 секунды)
                    if i > 0:
                        await asyncio.sleep(2)

                    wb_api = CurrentStatistics(account.api_key)
                    stats = await wb_api.get_today_stats_for_message()

                    orders_quantity = stats["orders"]["quantity"]
                    orders_amount = stats["orders"]["amount"]
                    sales_quantity = stats["sales"]["quantity"]
                    sales_amount = stats["sales"]["amount"]

                    formatted_orders_amount = f"{orders_amount:,.0f} ₽".replace(",", " ").replace(".", ",")
                    formatted_sales_amount = f"{sales_amount:,.2f} ₽".replace(",", " ").replace(".", ",")

                    stats_text += f"<b>{account_display_name}</b>\n"
                    stats_text += f"Заказы: <b>{orders_quantity}</b> шт. на <b>{formatted_orders_amount}</b>\n"
                    stats_text += f"Выкупы: <b>{sales_quantity}</b> шт. на <b>{formatted_sales_amount}</b>\n\n"

                    successful_accounts += 1

                except Exception as e:
                    error_message = str(e)

                    # Извлекаем только конкретную причину ошибки
                    if "Неверный API ключ" in error_message:
                        display_error = "Неверный API ключ"
                    elif "Слишком много запросов" in error_message or "429" in error_message:
                        display_error = "Превышен лимит запросов"
                        rate_limited_accounts += 1
                    elif "Таймаут" in error_message:
                        display_error = "Таймаут запроса"
                    else:
                        display_error = "Ошибка подключения"

                    stats_text += f"<b>{account_display_name}</b>\n"
                    stats_text += f"{display_error}\n\n"

            # Добавляем подсказку только если есть ошибки лимита
            if rate_limited_accounts > 0:
                stats_text += "<i>При превышении лимита повторите запрос через 1-2 минуты</i>"

            return stats_text

    async def send_scheduled_report(self, scheduled_time: str):
        """Отправить отчет всем администраторам в личные чаты"""
        try:
            # Получаем список администраторов
            admin_users = await self.get_admin_users_from_chat()

            if not admin_users:
                logger.warning("Не найдено администраторов для отправки отчета")
                return

            # Получаем статистику (один раз для всех)
            message = await self.get_daily_stats_message(scheduled_time)
            successful_sends = 0
            failed_sends = 0

            # Отправляем каждому администратору в личный чат
            for admin in admin_users:
                try:
                    await self.bot.send_message(admin.id, message)
                    logger.info(
                        f"Автоотчет {scheduled_time} отправлен пользователю {admin.first_name} (ID: {admin.id})")
                    successful_sends += 1

                    # Небольшая задержка между отправками, чтобы не превысить лимиты Telegram
                    await asyncio.sleep(0.5)

                except Exception as e:
                    logger.error(
                        f"Ошибка при отправке автоотчета пользователю {admin.first_name} (ID: {admin.id}): {e}")
                    failed_sends += 1

            logger.info(
                f"Итоги отправки автоотчета {scheduled_time}: успешно {successful_sends}, ошибок {failed_sends}")

        except Exception as e:
            logger.error(f"Ошибка при подготовке автоотчета {scheduled_time}: {e}")

    def get_moscow_time(self):
        """Получить текущее московское время"""
        return datetime.now(self.moscow_tz)

    async def start_scheduler(self):
        """Запустить планировщик отчетов"""
        logger.info("Планировщик автоотчетов запущен")
        logger.info(f"Отчеты будут приходить в личные чаты администраторов из группы (ID: {self.admin_chat_id})")
        logger.info(f"Используется временная зона: {self.moscow_tz}")

        # Время отправки автоотчетов (московское время)
        target_times = [
            (7, 0),  # 7:00 МСК
            (12, 0),  # 12:00 МСК
            (19, 0)  # 19:00 МСК
        ]

        while True:
            # Используем московское время для проверки
            now = self.get_moscow_time()

            # Логируем текущее время для отладки (раз в 30 минут)
            if now.minute == 0 and now.second < 30:
                logger.debug(f"Текущее московское время: {now.strftime('%H:%M:%S')}")

            # Проверяем все целевые времена
            for target_hour, target_minute in target_times:
                if now.hour == target_hour and now.minute == target_minute:
                    scheduled_time = f"{target_hour}:{target_minute:02d} МСК"
                    logger.info(f"Время автоотчета: {scheduled_time}")
                    logger.info(f"Текущее серверное время UTC: {datetime.utcnow().strftime('%H:%M:%S')}")
                    logger.info(f"Текущее московское время: {now.strftime('%H:%M:%S')}")

                    try:
                        await self.send_scheduled_report(scheduled_time)
                        logger.info(f"Автоотчет {scheduled_time} обработан")
                    except Exception as e:
                        logger.error(f"Ошибка при обработке автоотчета {scheduled_time}: {e}")

                    # Ждем 61 секунду чтобы не отправить повторно
                    await asyncio.sleep(61)
                    break

            # Ждем 30 секунд до следующей проверки
            await asyncio.sleep(30)
