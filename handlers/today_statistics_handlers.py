# handlers/today_statistics_handlers.py
import asyncio
import logging
from datetime import datetime, timedelta
from aiogram import Router, F
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession
from database.account_manager import AccountManager
from functions.today_product_statistics import TodayProductStatistics
from keyboards.statistics_kb import get_stats_keyboard

logger = logging.getLogger(__name__)

today_stats_router = Router()


def format_currency(amount: float) -> str:
    """Форматирование суммы с пробелом-разделителем тысяч и символом рубля"""
    # Форматируем с 2 знаками после запятой
    formatted = f"{amount:,.2f}"
    # Заменяем запятые на пробелы (разделитель тысяч)
    formatted = formatted.replace(",", " ")
    # Заменяем точку на запятую (десятичный разделитель)
    formatted = formatted.replace(".", ",")
    return f"{formatted} ₽"


@today_stats_router.callback_query(F.data == "today_quick_stats")
async def handle_today_quick_stats(callback: CallbackQuery, session: AsyncSession):
    """Быстрая сводка за сегодня (только первый магазин)"""

    await callback.answer()

    try:
        loading_msg = await callback.message.answer(
            "⚡ <b>Получение быстрой сводки за сегодня...</b>"
        )

        account_manager = AccountManager(session)
        all_accounts = await account_manager.get_all_accounts()

        if not all_accounts:
            await loading_msg.delete()
            await callback.message.answer(
                "❌ <b>Нет добавленных магазинов</b>",
                reply_markup=get_stats_keyboard()
            )
            return

        # Получаем дату сегодняшнего дня
        today_date_obj = datetime.now()
        date_str = today_date_obj.strftime("%d.%m.%Y")

        await loading_msg.delete()

        # Быстрая сводка - собираем данные только по первому магазину
        first_account = all_accounts[0]
        account_name = first_account.account_name or f"Магазин {first_account.id}"

        try:
            today_stats = TodayProductStatistics(first_account.api_key)
            summary = await today_stats.get_today_product_stats_summary()

            if summary["has_data"]:
                # Форматируем суммы
                order_sum_formatted = format_currency(summary['total_order_sum'])
                buyout_sum_formatted = format_currency(summary['total_buyout_sum'])

                # Формируем сообщение в нужном формате
                result_message = "<b>📊 Быстрая сводка</b>\n\n"
                result_message += f"<b>📅 За сегодня ({date_str})</b>\n\n"
                result_message += f"<b>{account_name}</b>\n"
                result_message += f"🛒 <b>Заказы:</b> {summary['total_orders']:,} шт. на {order_sum_formatted}\n"
                result_message += f"📈 <b>Выкупы:</b> {summary['total_buyouts']:,} шт. на {buyout_sum_formatted}\n"
            else:
                result_message = "<b>📊 Быстрая сводка</b>\n\n"
                result_message += f"<b>📅 За сегодня ({date_str})</b>\n\n"
                result_message += f"<b>{account_name}</b>\n"
                result_message += f"📭 <b>Нет данных за сегодня</b>\n"
                result_message += f"<i>Причина:</i> {summary.get('error', 'Неизвестно')}"

        except Exception as e:
            error_message = str(e)
            if "Неверный API ключ" in error_message:
                display_error = "❌ Неверный API ключ"
            else:
                display_error = "⚠️ Ошибка получения данных"

            result_message = "<b>📊 Быстрая сводка</b>\n\n"
            result_message += f"<b>📅 За сегодня ({date_str})</b>\n\n"
            result_message += f"<b>{account_name}</b>\n"
            result_message += f"❌ <b>{display_error}</b>\n"
            result_message += f"<i>Причина:</i> {error_message[:80]}"

        await callback.message.answer(
            result_message,
            reply_markup=get_stats_keyboard()
        )

    except Exception as e:
        logger.error(f"Ошибка при получении быстрой сводки: {e}")
        await callback.message.answer(
            f"<b>❌ Ошибка:</b> {str(e)[:100]}",
            reply_markup=get_stats_keyboard()
        )
