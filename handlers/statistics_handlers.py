# statistics_handlers.py
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

    # Показываем сообщение о загрузке
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

        # Получаем текущую дату
        today = datetime.now().strftime("%d.%m.%Y")

        # Формируем общее сообщение со статистикой всех магазинов
        stats_text = f"📊 <b>Статистика всех магазинов</b>\n\n"
        stats_text += f"📅 За сегодня (<b>{today}</b>)\n\n"

        successful_accounts = 0
        failed_accounts = 0

        # Собираем статистику по каждому магазину
        for account in all_accounts:
            account_display_name = account.account_name or f"Магазин {account.id}"

            try:
                wb_api = WBAPI(account.api_key)
                stats = await wb_api.get_today_stats_for_message()

                orders_quantity = stats["orders"]["quantity"]
                orders_amount = stats["orders"]["amount"]
                sales_quantity = stats["sales"]["quantity"]
                sales_amount = stats["sales"]["amount"]

                # Форматируем суммы
                formatted_orders_amount = f"{orders_amount:,.0f} ₽".replace(",", " ").replace(".", ",")
                formatted_sales_amount = f"{sales_amount:,.2f} ₽".replace(",", " ").replace(".", ",")

                # Добавляем статистику магазина в общее сообщение
                stats_text += f"<b>{account_display_name}</b>\n"
                stats_text += f"🛒 Заказы: <b>{orders_quantity}</b> шт. на <b>{formatted_orders_amount}</b>\n"
                stats_text += f"📈 Выкупы: <b>{sales_quantity}</b> шт. на <b>{formatted_sales_amount}</b>\n\n"

                successful_accounts += 1

            except Exception as e:
                logger.error(f"Ошибка при получении статистики для {account_display_name}: {str(e)}")
                # Добавляем более детальную информацию об ошибке
                error_message = str(e)
                if "Неверный API ключ" in error_message:
                    detailed_error = "Неверный API ключ"
                elif "Таймаут" in error_message:
                    detailed_error = "Таймаут запроса"
                elif "Слишком много запросов" in error_message:
                    detailed_error = "Превышен лимит запросов"
                elif "401" in error_message:
                    detailed_error = "Ошибка авторизации (401)"
                elif "429" in error_message:
                    detailed_error = "Слишком много запросов (429)"
                else:
                    detailed_error = f"Ошибка: {error_message[:50]}..." if len(
                        error_message) > 50 else f"Ошибка: {error_message}"

                stats_text += f"<b>{account_display_name}</b>\n"
                stats_text += f"❌ {detailed_error}\n\n"
                failed_accounts += 1

        # УДАЛЯЕМ сообщение о загрузке и отправляем новое с результатами
        await loading_msg.delete()
        await message.answer(
            stats_text,
            reply_markup=get_main_keyboard()
        )

    except Exception as e:
        logger.error(f"Неожиданная ошибка при получении статистики: {e}")
        await loading_msg.delete()
        await message.answer(
            "❌ <b>Произошла непредвиденная ошибка</b>\n\n"
            "<i>Попробуйте позже</i>",
            reply_markup=get_main_keyboard()
        )
