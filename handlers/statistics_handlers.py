# statistics_handlers.py
import asyncio
from aiogram import Router, F
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession
from database.account_manager import AccountManager
from functions.wb_api import WBAPI
from keyboards.main_kb import get_main_keyboard
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

statistics_router = Router()


@statistics_router.message(F.text == "📊 Статистика")
async def show_all_accounts_stats(message: Message, session: AsyncSession):
    """Показать статистику всех магазинов"""

    loading_msg = await message.answer(
        "📊 <b>Получение статистики...</b>\n\n"
        "🔄 Загружаем данные по всем магазинам...",
        reply_markup=get_main_keyboard()
    )

    try:
        account_manager = AccountManager(session)
        all_accounts = await account_manager.get_all_accounts()

        if not all_accounts:
            await loading_msg.delete()
            await message.answer(
                "❌ <b>Нет добавленных магазинов</b>\n\n"
                "Перейдите в настройки, чтобы добавить первый магазин.",
                reply_markup=get_main_keyboard()
            )
            return

        today = datetime.now().strftime("%d.%m.%Y")
        stats_text = f"📊 <b>Статистика всех магазинов</b>\n\n"
        stats_text += f"📅 За сегодня (<b>{today}</b>)\n\n"

        successful_accounts = 0
        rate_limited_accounts = 0

        # Добавляем задержки между запросами к разным магазинам
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
                    # Для всех остальных ошибок показываем общее сообщение
                    display_error = "Ошибка подключения"

                stats_text += f"<b>{account_display_name}</b>\n"
                stats_text += f"❌ {display_error}\n\n"

        # Добавляем подсказку только если есть ошибки лимита
        if rate_limited_accounts > 0:
            stats_text += "💡 <i>При превышении лимита повторите запрос через 1-2 минуты</i>"

        await loading_msg.delete()
        await message.answer(stats_text, reply_markup=get_main_keyboard())

    except Exception as e:
        logger.error(f"Неожиданная ошибка: {e}")
        await loading_msg.delete()
        await message.answer(
            "❌ <b>Произошла непредвиденная ошибка</b>\n\n"
            "<i>Попробуйте позже</i>",
            reply_markup=get_main_keyboard()
        )
