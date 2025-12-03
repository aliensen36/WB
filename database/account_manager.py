# database/account_manager.py
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from database.models import SellerAccount
from typing import List, Optional


class AccountManager:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_account(self, api_key: str, account_name: Optional[str] = None) -> SellerAccount:
        """Создание нового магазина"""
        # Валидация API ключа
        if not api_key or len(api_key) < 10:
            raise ValueError("Некорректный API ключ")

        # Проверяем, нет ли уже такого API ключа
        existing_stmt = select(SellerAccount).where(SellerAccount.api_key == api_key)
        existing_result = await self.session.execute(existing_stmt)
        if existing_result.scalar_one_or_none():
            raise ValueError("Этот API ключ уже используется")

        # Создаем аккаунт
        new_account = SellerAccount(
            api_key=api_key,
            account_name=account_name
        )

        self.session.add(new_account)
        await self.session.commit()
        await self.session.refresh(new_account)

        print(f"✅ Создан новый магазин: {new_account.account_name or 'Без названия'}")
        return new_account

    async def get_all_accounts(self) -> List[SellerAccount]:
        """Получение всех магазинов"""
        stmt = select(SellerAccount).order_by(SellerAccount.created.desc())
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_account_by_id(self, account_id: int) -> Optional[SellerAccount]:
        """Получение конкретного магазина"""
        stmt = select(SellerAccount).where(SellerAccount.id == account_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def delete_account(self, account_id: int) -> bool:
        """Удаление магазина (полное удаление из БД)"""
        account = await self.get_account_by_id(account_id)
        if account:
            await self.session.delete(account)
            await self.session.commit()
            return True
        return False

    async def update_account_name(self, account_id: int, new_name: str) -> Optional[SellerAccount]:
        """Обновление названия магазина"""
        account = await self.get_account_by_id(account_id)
        if account:
            account.account_name = new_name
            await self.session.commit()
            await self.session.refresh(account)
            return account
        return None

    async def get_account_by_api_key(self, api_key: str) -> Optional[SellerAccount]:
        """Получение магазина по API ключу"""
        stmt = select(SellerAccount).where(SellerAccount.api_key == api_key)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_accounts_count(self) -> int:
        """Получение количества магазинов"""
        stmt = select(SellerAccount)
        result = await self.session.execute(stmt)
        return len(list(result.scalars().all()))