from aiogram.fsm.state import StatesGroup, State


# Состояния для создания кабинета
class AddAccountStates(StatesGroup):
    waiting_for_api_key = State()
    waiting_for_account_name = State()


# Состояния для управления кабинетом
class AccountManagementStates(StatesGroup):
    waiting_account_name = State()        # Ожидание ввода имени аккаунта
    waiting_api_key = State()             # Ожидание ввода API ключа
    waiting_rename = State()              # Ожидание нового названия магазина
    waiting_product_rename = State()      # Ожидание нового названия продукта
