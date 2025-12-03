from aiogram.fsm.state import StatesGroup, State


# Состояния для создания магазина
class AddAccountStates(StatesGroup):
    waiting_for_api_key = State()
    waiting_for_account_name = State()


# Состояния для управления магазином
class AccountManagementStates(StatesGroup):
    waiting_account_name = State()
    waiting_api_key = State()
    waiting_rename = State()

