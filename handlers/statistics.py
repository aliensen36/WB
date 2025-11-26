import time
import asyncio
from datetime import datetime, timedelta
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from FSM.states import StatsStates
from functions.statistics_f import format_stats_response, format_incomes_response, format_stocks_response
from keyboards.statistics_kb import get_main_keyboard, get_period_keyboard
from functions.orders import get_stocks, get_incomes, analyze_sales_stats, get_24h_orders_stats, analyze_orders_stats, \
    get_orders_by_date, get_sales, get_all_orders
from functions.sales import get_all_sales

stats_router = Router()


async def send_terminal_message(message: Message, text: str, delay: float = 0.5):
    """Отправляет сообщение в стиле терминала с задержкой"""
    await asyncio.sleep(delay)  # Задержка между сообщениями
    await message.answer(f"<code>{text}</code>")


@stats_router.message(Command("stats"))
async def cmd_stats(message: Message):
    await message.answer(
        "📊 <b>Меню статистики</b>\n\n"
        "Выберите тип отчета:",
        reply_markup=get_main_keyboard()
    )


@stats_router.message(F.text == "📊 Статистика за сегодня")
async def today_stats(message: Message):
    await send_terminal_message(message, "🚀 <b>Запуск сбора статистики за сегодня</b>", delay=0)

    today = datetime.now().strftime('%Y-%m-%d')

    # Получаем данные с детальным прогрессом
    await send_terminal_message(message, f"📦 Запрос заказов за {today} (flag=1)...")
    orders = get_orders_by_date(today, flag=1)

    if orders:
        await send_terminal_message(message, f"✅ Получено {len(orders)} заказов за {today}")
    else:
        await send_terminal_message(message, "❌ Не удалось получить данные о заказах")

    await send_terminal_message(message, "⏳ Ожидание 60 сек для соблюдения лимитов API...")
    time.sleep(60)

    await send_terminal_message(message, f"💰 Запрос продаж за {today} (flag=1)...")
    sales = get_sales(today, flag=1)

    if sales:
        await send_terminal_message(message, f"✅ Получено {len(sales)} продаж")
    else:
        await send_terminal_message(message, "❌ Не удалось получить данные о продажах")

    # Анализируем
    await send_terminal_message(message, "📈 Анализ полученных данных...")
    orders_stats = analyze_orders_stats(orders or [])
    sales_stats = analyze_sales_stats(sales or [])

    # Формируем ответ
    await send_terminal_message(message, "📊 Формирование отчета...")
    response = format_stats_response(orders_stats, sales_stats, "сегодня")

    await send_terminal_message(message, "✅ <b>Отчет готов!</b>")
    await asyncio.sleep(1)  # Дополнительная задержка перед отправкой отчета
    await message.answer(response, reply_markup=get_main_keyboard())


@stats_router.message(F.text == "📈 Статистика за вчера")
async def yesterday_stats(message: Message):
    await send_terminal_message(message, "🚀 <b>Запуск сбора статистики за вчера</b>", delay=0)

    yesterday = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')

    await send_terminal_message(message, f"📦 Запрос заказов за {yesterday} (flag=1)...")
    orders = get_orders_by_date(yesterday, flag=1)

    if orders:
        await send_terminal_message(message, f"✅ Получено {len(orders)} заказов за {yesterday}")
    else:
        await send_terminal_message(message, "❌ Не удалось получить данные о заказах")

    await send_terminal_message(message, "⏳ Ожидание 60 сек для соблюдения лимитов API...")
    time.sleep(60)

    await send_terminal_message(message, f"💰 Запрос продаж за {yesterday} (flag=1)...")
    sales = get_sales(yesterday, flag=1)

    if sales:
        await send_terminal_message(message, f"✅ Получено {len(sales)} продаж")
    else:
        await send_terminal_message(message, "❌ Не удалось получить данные о продажах")

    orders_stats = analyze_orders_stats(orders or [])
    sales_stats = analyze_sales_stats(sales or [])

    await send_terminal_message(message, "📊 Формирование отчета...")
    response = format_stats_response(orders_stats, sales_stats, "вчера")

    await send_terminal_message(message, "✅ <b>Отчет готов!</b>")
    await asyncio.sleep(1)
    await message.answer(response, reply_markup=get_main_keyboard())


@stats_router.message(F.text == "🕐 Статистика за 24 часа")
async def last24h_stats(message: Message):
    await send_terminal_message(message, "🚀 <b>Запуск сбора статистики за 24 часа</b>", delay=0)

    await send_terminal_message(message, "🕐 Получение заказов за последние 24 часа...")
    orders = get_24h_orders_stats()

    if orders:
        await send_terminal_message(message, f"✅ Получено {len(orders)} заказов за 24 часа")
    else:
        await send_terminal_message(message, "❌ Не удалось получить данные о заказах")

    await send_terminal_message(message, "📈 Анализ данных...")
    sales_stats = analyze_sales_stats([])
    orders_stats = analyze_orders_stats(orders)

    await send_terminal_message(message, "📊 Формирование отчета...")
    response = format_stats_response(orders_stats, sales_stats, "24 часа")

    await send_terminal_message(message, "✅ <b>Отчет готов!</b>")
    await asyncio.sleep(1)
    await message.answer(response, reply_markup=get_main_keyboard())


@stats_router.message(F.text == "🚚 Поставки")
async def incomes_stats(message: Message):
    await send_terminal_message(message, "🚀 <b>Запуск сбора данных о поставках</b>", delay=0)

    date_from = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')

    await send_terminal_message(message, f"🚚 Запрос поставок с {date_from}...")
    incomes = get_incomes(date_from)

    if incomes:
        await send_terminal_message(message, f"✅ Получено {len(incomes)} поставок")
    else:
        await send_terminal_message(message, "❌ Не удалось получить данные о поставках")

    await send_terminal_message(message, "📊 Формирование отчета...")
    response = format_incomes_response(incomes or [])

    await send_terminal_message(message, "✅ <b>Отчет готов!</b>")
    await asyncio.sleep(1)
    await message.answer(response, reply_markup=get_main_keyboard())


@stats_router.message(F.text == "📦 Остатки")
async def stocks_stats(message: Message):
    await send_terminal_message(message, "🚀 <b>Запуск сбора данных об остатках</b>", delay=0)

    await send_terminal_message(message, "📦 Запрос остатков...")
    stocks = get_stocks()

    if stocks:
        await send_terminal_message(message, f"✅ Получено {len(stocks)} записей об остатках")
    else:
        await send_terminal_message(message, "❌ Не удалось получить данные об остатках")

    await send_terminal_message(message, "📊 Формирование отчета...")
    response = format_stocks_response(stocks or [])

    await send_terminal_message(message, "✅ <b>Отчет готов!</b>")
    await asyncio.sleep(1)
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
    await send_terminal_message(message, f"🚀 <b>Запуск сбора статистики за {period_text.lower()}</b>", delay=0)

    # Определяем дату начала периода
    today = datetime.now()
    if period_text == "Сегодня":
        date_from = today.strftime('%Y-%m-%d')
        await send_terminal_message(message, f"📦 Запрос заказов за {date_from} (flag=1)...")
        orders = get_orders_by_date(date_from, flag=1)

        if orders:
            await send_terminal_message(message, f"✅ Получено {len(orders)} заказов за {date_from}")

        await send_terminal_message(message, "⏳ Ожидание 60 сек для соблюдения лимитов API...")
        time.sleep(60)

        await send_terminal_message(message, f"💰 Запрос продаж за {date_from} (flag=1)...")
        sales = get_sales(date_from, flag=1)

        if sales:
            await send_terminal_message(message, f"✅ Получено {len(sales)} продаж")

    elif period_text == "Вчера":
        date_from = (today - timedelta(days=1)).strftime('%Y-%m-%d')
        await send_terminal_message(message, f"📦 Запрос заказов за {date_from} (flag=1)...")
        orders = get_orders_by_date(date_from, flag=1)

        if orders:
            await send_terminal_message(message, f"✅ Получено {len(orders)} заказов за {date_from}")

        await send_terminal_message(message, "⏳ Ожидание 60 сек для соблюдения лимитов API...")
        time.sleep(60)

        await send_terminal_message(message, f"💰 Запрос продаж за {date_from} (flag=1)...")
        sales = get_sales(date_from, flag=1)

        if sales:
            await send_terminal_message(message, f"✅ Получено {len(sales)} продаж")

    else:  # Для периодов 3/7/30 дней используем другой подход
        if period_text == "3 дня":
            date_from = (today - timedelta(days=3)).strftime('%Y-%m-%d')
            period_desc = "3 дня"
        elif period_text == "7 дней":
            date_from = (today - timedelta(days=7)).strftime('%Y-%m-%d')
            period_desc = "7 дней"
        else:  # 30 дней
            date_from = (today - timedelta(days=30)).strftime('%Y-%m-%d')
            period_desc = "30 дней"

        await send_terminal_message(message, f"📦 Запрос заказов за {period_desc} (пагинация)...")
        orders = get_all_orders(date_from)

        if orders:
            await send_terminal_message(message, f"✅ Получено {len(orders)} заказов за {period_desc}")

        await send_terminal_message(message, "⏳ Ожидание 60 сек для соблюдения лимитов API...")
        time.sleep(60)

        await send_terminal_message(message, f"💰 Запрос продаж за {period_desc} (пагинация)...")
        sales = get_all_sales(date_from)

        if sales:
            await send_terminal_message(message, f"✅ Получено {len(sales)} продаж за {period_desc}")

    # Анализируем
    await send_terminal_message(message, "📈 Анализ полученных данных...")
    orders_stats = analyze_orders_stats(orders or [])
    sales_stats = analyze_sales_stats(sales or [])

    await send_terminal_message(message, "📊 Формирование отчета...")
    response = format_stats_response(orders_stats, sales_stats, period_text.lower())

    await send_terminal_message(message, "✅ <b>Отчет готов!</b>")
    await asyncio.sleep(1)
    await message.answer(response, reply_markup=get_main_keyboard())
    await state.clear()


@stats_router.message(StatsStates.choosing_period, F.text == "↩️ Назад")
async def back_to_main(message: Message, state: FSMContext):
    await message.answer(
        "📊 <b>Главное меню</b>",
        reply_markup=get_main_keyboard()
    )
    await state.clear()