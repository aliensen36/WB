# handlers/sales_funnel_handlers.py
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, FSInputFile
from aiogram.filters import Command
from aiogram.utils.keyboard import InlineKeyboardBuilder, InlineKeyboardButton
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime, timedelta
import logging
from keyboards.main_kb import get_main_keyboard
from wb_api_client.sales_funnel_service import SalesFunnelService

logger = logging.getLogger(__name__)

sales_funnel_router = Router()


@sales_funnel_router.message(Command("funnel"))
async def cmd_funnel(message: Message, session: AsyncSession):
    """Команда для получения воронки продаж"""
    builder = InlineKeyboardBuilder()

    builder.row(
        InlineKeyboardButton(text="📅 Вчерашний день", callback_data="funnel_yesterday"),
        InlineKeyboardButton(text="📊 Последние 7 дней", callback_data="funnel_7")
    )
    builder.row(
        InlineKeyboardButton(text="📈 Последние 30 дней", callback_data="funnel_30"),
        InlineKeyboardButton(text="📁 Мои отчеты", callback_data="funnel_reports")
    )
    builder.row(
        InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_main")
    )

    await message.answer(
        "📊 <b>Воронка продаж</b>\n\n"
        "Выберите период для анализа:\n"
        "• 📅 Вчерашний день - данные за вчера\n"
        "• 📊 7 дней - недельный отчет\n"
        "• 📈 30 дней - месячный отчет\n"
        "• 📁 Мои отчеты - скачать сохраненные файлы",
        reply_markup=builder.as_markup()
    )


# Добавьте ЭТУ команду тут (после cmd_funnel и перед handle_funnel_period):
@sales_funnel_router.message(Command("yesterday"))
async def cmd_yesterday(message: Message, session: AsyncSession):
    """Быстрое получение отчета за вчерашний день"""
    builder = InlineKeyboardBuilder()

    builder.row(
        InlineKeyboardButton(text="📅 Получить за вчера", callback_data="funnel_yesterday"),
        InlineKeyboardButton(text="📁 Мои отчеты", callback_data="funnel_reports")
    )
    builder.row(
        InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_main")
    )

    yesterday = datetime.now() - timedelta(days=1)
    date_str = yesterday.strftime("%d.%m.%Y")

    await message.answer(
        f"📅 <b>Отчет за вчерашний день</b>\n\n"
        f"<b>Дата:</b> {date_str}\n\n"
        f"Получите данные воронки продаж за вчерашний день:",
        reply_markup=builder.as_markup()
    )


@sales_funnel_router.callback_query(F.data.startswith("funnel_"))
async def handle_funnel_period(callback: CallbackQuery, session: AsyncSession):
    """Обработка выбора периода"""
    data = callback.data

    if data == "funnel_yesterday":
        period_type = "yesterday"
        period_name = "вчерашний день"
        days = 1
    elif data == "funnel_7":
        period_type = "7_days"
        period_name = "7 дней"
        days = 7
    elif data == "funnel_30":
        period_type = "30_days"
        period_name = "30 дней"
        days = 30
    else:
        await callback.answer("Выберите магазин для отчета")
        return

    # Сохраняем данные о периоде в callback
    await callback.answer()

    # Получаем список аккаунтов
    service = SalesFunnelService(session)
    accounts = await service.get_accounts_list()

    if not accounts:
        builder = InlineKeyboardBuilder()
        builder.add(InlineKeyboardButton(text="⚙️ Добавить магазин", callback_data="manage_shops"))
        builder.add(InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_funnel"))
        builder.adjust(1)

        await callback.message.edit_text(
            "❌ <b>Нет доступных магазинов</b>\n\n"
            "Сначала добавьте магазин в настройках.",
            reply_markup=builder.as_markup()
        )
        return

    builder = InlineKeyboardBuilder()
    for account in accounts:
        account_name = account.get('account_name') or f"Магазин {account.get('id')}"
        builder.add(InlineKeyboardButton(
            text=f"🏪 {account_name}",
            callback_data=f"run_funnel_{account.get('id')}_{period_type}"
        ))
    builder.add(InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_funnel"))
    builder.adjust(1)

    await callback.message.edit_text(
        f"📊 <b>Воронка продаж за {period_name}</b>\n\n"
        "Выберите магазин для анализа:",
        reply_markup=builder.as_markup()
    )


@sales_funnel_router.callback_query(F.data.startswith("run_funnel_"))
async def run_funnel_analysis(callback: CallbackQuery, session: AsyncSession):
    """Запуск анализа воронки продаж"""
    try:
        parts = callback.data.split("_")
        account_id = int(parts[2])
        period_type = parts[3]  # yesterday, 7_days, 30_days

        # Определяем название периода
        if period_type == "yesterday":
            period_name = "вчерашний день"
            yesterday = datetime.now() - timedelta(days=1)
            date_str = yesterday.strftime("%d.%m.%Y")
        elif period_type == "7_days":
            period_name = "7 дней"
            end_date = datetime.now()
            start_date = end_date - timedelta(days=6)
            date_str = f"{start_date.strftime('%d.%m.%Y')} - {end_date.strftime('%d.%m.%Y')}"
        elif period_type == "30_days":
            period_name = "30 дней"
            end_date = datetime.now()
            start_date = end_date - timedelta(days=29)
            date_str = f"{start_date.strftime('%d.%m.%Y')} - {end_date.strftime('%d.%m.%Y')}"
        else:
            period_name = "период"
            date_str = ""

        processing_msg = await callback.message.answer(
            f"⏳ <b>Запускаю анализ воронки продаж...</b>\n\n"
            f"📅 <b>Период:</b> {period_name}\n"
            f"📆 <b>Дата:</b> {date_str}\n"
            f"🏪 <b>Магазин:</b> ID {account_id}\n\n"
            f"<i>Это может занять несколько минут...</i>"
        )

        service = SalesFunnelService(session)

        # Получаем данные
        result = await service.fetch_all_with_pagination(
            account_id=account_id,
            period_type=period_type,
            max_products=1000
        )

        if not result.get("success"):
            error_msg = result.get('error', 'Неизвестная ошибка')

            error_text = (
                f"❌ <b>Ошибка при получении данных</b>\n\n"
                f"<b>Магазин:</b> ID {account_id}\n"
                f"<b>Период:</b> {period_name}\n"
                f"<b>Ошибка:</b> {error_msg}\n\n"
            )

            if "API" in error_msg or "ключ" in error_msg.lower():
                error_text += "<i>Проверьте API ключ в настройках магазина.</i>"
            elif "сеть" in error_msg.lower() or "timeout" in error_msg.lower():
                error_text += "<i>Проблемы с подключением к интернету. Попробуйте позже.</i>"
            else:
                error_text += "<i>Попробуйте позже или выберите другой период.</i>"

            await processing_msg.edit_text(error_text)
            return

        file_info = result.get("file_info", {})
        total_products = result.get("total_products", 0)

        # Получаем общую статистику
        products = result.get("data", {}).get("data", {}).get("products", [])

        total_orders = 0
        total_order_sum = 0
        total_open = 0
        total_cart = 0

        for product in products:
            statistic = product.get("statistic", {})
            selected = statistic.get("selected", {})

            total_orders += selected.get('orderCount', 0)
            total_order_sum += selected.get('orderSum', 0)
            total_open += selected.get('openCount', 0)
            total_cart += selected.get('cartCount', 0)

        report_text = (
            f"✅ <b>Анализ завершен успешно!</b>\n\n"
            f"📅 <b>Период:</b> {period_name}\n"
            f"📆 <b>Дата:</b> {date_str}\n"
            f"🏪 <b>Магазин:</b> ID {account_id}\n\n"
            f"📊 <b>Статистика:</b>\n"
            f"• Товаров в отчете: <b>{total_products}</b>\n"
            f"• Всего открытий: <b>{total_open}</b>\n"
            f"• В корзину: <b>{total_cart}</b>\n"
            f"• Заказов: <b>{total_orders}</b>\n"
            f"• Сумма заказов: <b>{total_order_sum:,.0f} ₽</b>\n\n"
            f"⏰ <b>Время выполнения:</b> {datetime.now().strftime('%H:%M:%S')}\n\n"
            f"<b>Сохраненные файлы:</b>\n"
        )

        if file_info.get("json"):
            report_text += "• 📄 JSON (полные данные)\n"
        if file_info.get("csv"):
            report_text += "• 📊 CSV (основные данные)\n"
        if file_info.get("excel"):
            report_text += "• 📈 Excel (сводный отчет)\n"

        report_text += "\n<i>Для скачивания файлов нажмите на кнопку ниже.</i>"

        builder = InlineKeyboardBuilder()

        if file_info.get("csv"):
            builder.add(InlineKeyboardButton(
                text="📊 Скачать CSV",
                callback_data=f"send_file_csv_{account_id}"
            ))

        if file_info.get("excel"):
            builder.add(InlineKeyboardButton(
                text="📈 Скачать Excel",
                callback_data=f"send_file_excel_{account_id}"
            ))

        builder.add(InlineKeyboardButton(
            text="📄 Скачать JSON",
            callback_data=f"send_file_json_{account_id}"
        ))

        builder.row(
            InlineKeyboardButton(
                text="🔄 Новый отчет",
                callback_data=f"funnel_{period_type}"
            ),
            InlineKeyboardButton(
                text="📁 Все отчеты",
                callback_data=f"list_reports_{account_id}"
            )
        )

        builder.row(
            InlineKeyboardButton(
                text="🏠 В главное меню",
                callback_data="back_to_main"
            )
        )

        await processing_msg.edit_text(
            report_text,
            reply_markup=builder.as_markup()
        )

    except Exception as e:
        logger.error(f"Error in funnel analysis: {e}", exc_info=True)
        await callback.message.answer(
            f"❌ <b>Критическая ошибка</b>\n\n"
            f"<code>{str(e)}</code>\n\n"
            f"<i>Пожалуйста, сообщите об ошибке разработчику.</i>"
        )


@sales_funnel_router.callback_query(F.data.startswith("send_file_"))
async def send_file_handler(callback: CallbackQuery, session: AsyncSession):
    """Отправить файл пользователю"""
    try:
        parts = callback.data.split("_")
        file_type = parts[2]  # csv, excel, json
        account_id = int(parts[3])

        service = SalesFunnelService(session)
        recent_files = await service.get_recent_files(account_id, limit=5)

        target_file = None
        for file_info in recent_files:
            if file_info['extension'] == f'.{file_type}':
                target_file = file_info['filepath']
                break

        if not target_file:
            await callback.answer("Файл не найден", show_alert=True)
            return

        try:
            file = FSInputFile(target_file)

            if file_type == 'csv':
                caption = "📊 CSV файл с данными воронки продаж"
            elif file_type == 'xlsx':
                caption = "📈 Excel файл с отчетом по воронке продаж"
            else:
                caption = "📄 JSON файл с полными данными"

            await callback.message.answer_document(
                document=file,
                caption=caption
            )
            await callback.answer("✅ Файл отправлен")

        except Exception as e:
            logger.error(f"Error sending file: {e}")
            await callback.answer("❌ Ошибка при отправке файла", show_alert=True)

    except Exception as e:
        logger.error(f"Error in send_file_handler: {e}")
        await callback.answer("❌ Произошла ошибка", show_alert=True)


@sales_funnel_router.callback_query(F.data == "funnel_reports")
async def show_recent_reports(callback: CallbackQuery, session: AsyncSession):
    """Показать недавние отчеты"""
    service = SalesFunnelService(session)
    accounts = await service.get_accounts_list()

    if not accounts:
        builder = InlineKeyboardBuilder()
        builder.add(InlineKeyboardButton(text="⚙️ Добавить магазин", callback_data="manage_shops"))
        builder.add(InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_funnel"))
        builder.adjust(1)

        await callback.message.edit_text(
            "❌ <b>Нет доступных магазинов</b>",
            reply_markup=builder.as_markup()
        )
        return

    builder = InlineKeyboardBuilder()
    for account in accounts:
        account_name = account.get('account_name') or f"Магазин {account.get('id')}"
        builder.add(InlineKeyboardButton(
            text=f"📁 {account_name}",
            callback_data=f"list_reports_{account.get('id')}"
        ))
    builder.add(InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_funnel"))
    builder.adjust(1)

    await callback.message.edit_text(
        "📁 <b>Мои отчеты</b>\n\n"
        "Выберите магазин для просмотра сохраненных отчетов:",
        reply_markup=builder.as_markup()
    )


@sales_funnel_router.callback_query(F.data.startswith("list_reports_"))
async def list_reports_for_account(callback: CallbackQuery, session: AsyncSession):
    """Показать отчеты для конкретного аккаунта"""
    account_id = int(callback.data.split("_")[2])

    service = SalesFunnelService(session)
    recent_files = await service.get_recent_files(account_id, limit=10)

    if not recent_files:
        await callback.message.edit_text(
            f"📭 <b>Нет сохраненных отчетов</b>\n\n"
            f"Для магазина ID {account_id} пока нет отчетов.\n"
            f"Создайте новый отчет с помощью команды /funnel"
        )
        return

    builder = InlineKeyboardBuilder()

    for file_info in recent_files:
        filename = file_info['filename']
        size_mb = file_info['size'] / 1024 / 1024

        if file_info['extension'] == '.csv':
            icon = '📊'
        elif file_info['extension'] == '.xlsx':
            icon = '📈'
        else:
            icon = '📄'

        button_text = f"{icon} {filename} ({size_mb:.1f} MB)"

        if len(button_text) > 50:
            button_text = button_text[:47] + "..."

        builder.add(InlineKeyboardButton(
            text=button_text,
            callback_data=f"send_file_{file_info['extension'][1:]}_{account_id}"
        ))

    builder.add(InlineKeyboardButton(text="⬅️ Назад", callback_data="funnel_reports"))
    builder.adjust(1)

    files_list = "\n".join([
        f"• {f['filename']} ({f['modified'].strftime('%d.%m.%Y %H:%M')})"
        for f in recent_files[:5]
    ])

    if len(recent_files) > 5:
        files_list += f"\n... и еще {len(recent_files) - 5}"

    await callback.message.edit_text(
        f"📁 <b>Сохраненные отчеты</b>\n\n"
        f"Магазин: ID {account_id}\n"
        f"Всего файлов: {len(recent_files)}\n\n"
        f"<b>Последние отчеты:</b>\n{files_list}\n\n"
        f"Нажмите на файл для отправки:",
        reply_markup=builder.as_markup()
    )


@sales_funnel_router.callback_query(F.data == "back_to_funnel")
async def back_to_funnel(callback: CallbackQuery, session: AsyncSession):
    """Вернуться к меню воронки продаж"""
    await cmd_funnel(callback.message, session)


@sales_funnel_router.callback_query(F.data == "back_to_main")
async def back_to_main(callback: CallbackQuery):
    """Вернуться в главное меню"""
    await callback.message.edit_text(
        "🏠 <b>Главное меню</b>",
        reply_markup=get_main_keyboard()
    )
