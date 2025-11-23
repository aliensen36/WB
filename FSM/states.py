from aiogram.fsm.state import StatesGroup, State


# Состояния для статистики
class StatsStates(StatesGroup):
    choosing_period = State()
    choosing_date = State()
