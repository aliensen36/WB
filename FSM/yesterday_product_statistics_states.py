# yesterday_product_statistics_states.py
from aiogram.fsm.state import StatesGroup, State


class StatisticsState(StatesGroup):
    waiting = State()
