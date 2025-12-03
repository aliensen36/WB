# FSM/product_states.py
from aiogram.fsm.state import StatesGroup, State


class ProductManagementStates(StatesGroup):
    """Состояния для управления товарами"""
    waiting_for_account_selection = State()  # Выбор магазина
    waiting_for_article_selection = State()  # Выбор артикула
    waiting_for_new_name = State()  # Ввод нового названия
