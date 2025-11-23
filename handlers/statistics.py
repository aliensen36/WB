import time
from datetime import datetime, timedelta  # timedelta импортирован отдельно
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from FSM.states import StatsStates
from functions.statistics_f import format_stats_response, format_incomes_response, format_stocks_response
from keyboards.statistics_kb import get_main_keyboard, get_period_keyboard
from orders import get_stocks, get_incomes, analyze_sales_stats, get_24h_orders_stats, analyze_orders_stats, \
    get_orders_by_date, get_sales, get_all_orders
from sales import get_all_sales

stats_router = Router()

@stats_router.message(Command("stats"))
async def cmd_stats(message: Message):
    await message.answer(
        "📊 <b>Меню статистики</b>\n\n"
        "Выберите тип отчета:",
        reply_markup=get_main_keyboard()
    )


@stats_router.message(F.text == "📊 Статистика за сегодня")
async def today_stats(message: Message):
    await message.answer("⏳ <i>Загружаю статистику за сегодня...</i>")

    today = datetime.now().strftime('%Y-%m-%d')

    # Получаем данные
    orders = get_orders_by_date(today, flag=1)
    time.sleep(60)  # Соблюдаем лимиты API
    sales = get_sales(today, flag=1)

    # Анализируем
    orders_stats = analyze_orders_stats(orders or [])
    sales_stats = analyze_sales_stats(sales or [])

    # Формируем ответ
    response = format_stats_response(orders_stats, sales_stats, "сегодня")
    await message.answer(response, reply_markup=get_main_keyboard())


@stats_router.message(F.text == "📈 Статистика за вчера")
async def yesterday_stats(message: Message):
    await message.answer("⏳ <i>Загружаю статистику за вчера...</i>")

    yesterday = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')  # ИСПРАВЛЕНО

    orders = get_orders_by_date(yesterday, flag=1)
    time.sleep(60)
    sales = get_sales(yesterday, flag=1)

    orders_stats = analyze_orders_stats(orders or [])
    sales_stats = analyze_sales_stats(sales or [])

    response = format_stats_response(orders_stats, sales_stats, "вчера")
    await message.answer(response, reply_markup=get_main_keyboard())


@stats_router.message(F.text == "🕐 Статистика за 24 часа")
async def last24h_stats(message: Message):
    await message.answer("⏳ <i>Загружаю статистику за 24 часа...</i>")

    orders = get_24h_orders_stats()
    sales_stats = analyze_sales_stats([])  # Для 24 часов продажи не получаем

    orders_stats = analyze_orders_stats(orders)

    response = format_stats_response(orders_stats, sales_stats, "24 часа")
    await message.answer(response, reply_markup=get_main_keyboard())


@stats_router.message(F.text == "🚚 Поставки")
async def incomes_stats(message: Message):
    await message.answer("⏳ <i>Загружаю данные о поставках...</i>")

    date_from = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')  # ИСПРАВЛЕНО
    incomes = get_incomes(date_from)

    response = format_incomes_response(incomes or [])
    await message.answer(response, reply_markup=get_main_keyboard())


@stats_router.message(F.text == "📦 Остатки")
async def stocks_stats(message: Message):
    await message.answer("⏳ <i>Загружаю данные об остатках...</i>")

    stocks = get_stocks()

    response = format_stocks_response(stocks or [])
    await message.answer(response, reply_markup=get_main_keyboard())


@stats_router.message(F.text == "📅 Выбрать период")
async def choose_period(message: Message, state: FSMContext):
    await message.answer(
        "📅 <b>Выберите период для статистики:</b>",
        reply_markup=get_period_keyboard()
    )
    await state.set_state(StatsStates.choosing_period)


@stats_router.message(StatsStates.choosing_period, F.text.in_(["Сегодня", "Вчера", "3 дня", "7 дней", "30 дней"]))
async def period_selected(message: Message, state: FSMContext):
    period_text = message.text
    await message.answer(f"⏳ <i>Загружаю статистику за {period_text.lower()}...</i>")

    # Определяем дату начала периода
    today = datetime.now()
    if period_text == "Сегодня":
        date_from = today.strftime('%Y-%m-%d')
        # Для одной даты используем flag=1
        orders = get_orders_by_date(date_from, flag=1)
        time.sleep(60)
        sales = get_sales(date_from, flag=1)

    elif period_text == "Вчера":
        date_from = (today - timedelta(days=1)).strftime('%Y-%m-%d')
        # Для одной даты используем flag=1
        orders = get_orders_by_date(date_from, flag=1)
        time.sleep(60)
        sales = get_sales(date_from, flag=1)

    else:  # Для периодов 3/7/30 дней используем другой подход
        if period_text == "3 дня":
            date_from = (today - timedelta(days=3)).strftime('%Y-%m-%d')
        elif period_text == "7 дней":
            date_from = (today - timedelta(days=7)).strftime('%Y-%m-%d')
        else:  # 30 дней
            date_from = (today - timedelta(days=30)).strftime('%Y-%m-%d')

        # Для периодов используем пагинацию с flag=0
        orders = get_all_orders(date_from)
        time.sleep(60)
        # Для продаж тоже нужно реализовать аналогичную функцию
        sales = get_all_sales(date_from)  # Нужно создать эту функцию!

    # Анализируем
    orders_stats = analyze_orders_stats(orders or [])
    sales_stats = analyze_sales_stats(sales or [])

    response = format_stats_response(orders_stats, sales_stats, period_text.lower())
    await message.answer(response, reply_markup=get_main_keyboard())
    await state.clear()


@stats_router.message(StatsStates.choosing_period, F.text == "↩️ Назад")
async def back_to_main(message: Message, state: FSMContext):
    await message.answer(
        "📊 <b>Главное меню</b>",
        reply_markup=get_main_keyboard()
    )
    await state.clear()
