from aiogram.fsm.state import StatesGroup, State


# Состояния для создания кабинета
class AddAccountStates(StatesGroup):
    waiting_for_api_key = State()
    waiting_for_account_name = State()


# Состояния для управления кабинетом
class AccountManagementStates(StatesGroup):
    managing_account = State()
    waiting_rename = State()
    waiting_delete_confirm = State()
