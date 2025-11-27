# scheduler.py
import asyncio
from aiogram import Bot
from sqlalchemy.ext.asyncio import AsyncSession
from database.account_manager import AccountManager
from functions.wb_api import WBAPI
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class StatisticsScheduler:
    def __init__(self, bot: Bot, session_maker):
        self.bot = bot
        self.session_maker = session_maker
        # Сохраняем ID вашего чата (замените на ваш реальный chat_id)
        self.your_chat_id = 1181445626  # Ваш chat_id из логов

    async def get_daily_stats_message(self, scheduled_time: str) -> str:
        """Сформировать сообщение со статистикой за сегодня для расписания"""
        async with self.session_maker() as session:
            account_manager = AccountManager(session)
            all_accounts = await account_manager.get_all_accounts()

            if not all_accounts:
                return "❌ <b>Нет добавленных магазинов</b>\n\nДобавьте магазины в настройках."

            today = datetime.now().strftime("%d.%m.%Y")

            # Добавляем заголовок для расписания
            stats_text = f"🕐 <b>Автоматический отчет ({scheduled_time})</b>\n\n"
            stats_text += f"📊 <b>Статистика всех магазинов</b>\n\n"
            stats_text += f"📅 За сегодня (<b>{today}</b>)\n\n"

            successful_accounts = 0
            rate_limited_accounts = 0

            # Собираем статистику по каждому магазину
            for i, account in enumerate(all_accounts):
                account_display_name = account.account_name or f"Магазин {account.id}"

                try:
                    # Задержка между запросами к разным аккаунтам (2 секунды)
                    if i > 0:
                        await asyncio.sleep(2)

                    wb_api = WBAPI(account.api_key)
                    stats = await wb_api.get_today_stats_for_message()

                    orders_quantity = stats["orders"]["quantity"]
                    orders_amount = stats["orders"]["amount"]
                    sales_quantity = stats["sales"]["quantity"]
                    sales_amount = stats["sales"]["amount"]

                    formatted_orders_amount = f"{orders_amount:,.0f} ₽".replace(",", " ").replace(".", ",")
                    formatted_sales_amount = f"{sales_amount:,.2f} ₽".replace(",", " ").replace(".", ",")

                    stats_text += f"<b>{account_display_name}</b>\n"
                    stats_text += f"🛒 Заказы: <b>{orders_quantity}</b> шт. на <b>{formatted_orders_amount}</b>\n"
                    stats_text += f"📈 Выкупы: <b>{sales_quantity}</b> шт. на <b>{formatted_sales_amount}</b>\n\n"

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
                    stats_text += f"❌ {display_error}\n\n"

            # Добавляем подсказку только если есть ошибки лимита
            if rate_limited_accounts > 0:
                stats_text += "💡 <i>При превышении лимита повторите запрос через 1-2 минуты</i>"

            return stats_text

    async def send_scheduled_report(self, scheduled_time: str):
        """Отправить отчет в ваш чат с ботом"""
        try:
            # Получаем статистику
            message = await self.get_daily_stats_message(scheduled_time)

            # Отправляем в ваш чат с ботом
            await self.bot.send_message(self.your_chat_id, message)
            logger.info(f"✅ Автоотчет {scheduled_time} отправлен в ваш чат с ботом")

        except Exception as e:
            logger.error(f"❌ Ошибка при отправке автоотчета {scheduled_time}: {e}")

    async def start_scheduler(self):
        """Запустить планировщик отчетов"""
        logger.info("🕐 Планировщик автоотчетов запущен")
        logger.info(f"💬 Отчеты будут приходить в ваш чат с ботом (ID: {self.your_chat_id})")

        # Время отправки автоотчетов
        target_times = [
            (7, 0),  # 7:00
            (12, 0),  # 12:00
            (19, 0)  # 19:00
        ]

        while True:
            now = datetime.now()

            # Проверяем все целевые времена
            for target_hour, target_minute in target_times:
                if now.hour == target_hour and now.minute == target_minute:
                    scheduled_time = f"{target_hour}:{target_minute:02d}"
                    logger.info(f"⏰ Время автоотчета: {scheduled_time}")

                    try:
                        await self.send_scheduled_report(scheduled_time)
                        logger.info(f"✅ Автоотчет {scheduled_time} отправлен")
                    except Exception as e:
                        logger.error(f"❌ Ошибка при отправке автоотчета {scheduled_time}: {e}")

                    # Ждем 61 секунду чтобы не отправить повторно
                    await asyncio.sleep(61)
                    break

            # Ждем 30 секунд до следующей проверки
            await asyncio.sleep(30)
