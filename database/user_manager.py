# database/user_manager.py
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from database.models import User
from datetime import datetime


class UserManager:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_or_create_user(self, tg_user) -> User:
        """
        Получение или создание пользователя из объекта Telegram User
        """
        # Ищем существующего пользователя
        stmt = select(User).where(User.tg_id == tg_user.id)
        result = await self.session.execute(stmt)
        existing_user = result.scalar_one_or_none()

        if existing_user:
            # Обновляем данные существующего пользователя
            await self._update_user_data(existing_user, tg_user)
            return existing_user
        else:
            # Создаем нового пользователя
            new_user = await self._create_new_user(tg_user)
            return new_user

    async def _update_user_data(self, user: User, tg_user):
        """
        Обновление данных существующего пользователя
        """
        update_data = {
            'first_name': tg_user.first_name,
            'last_name': tg_user.last_name,
            'username': tg_user.username,
        }

        await self.session.execute(
            update(User)
            .where(User.tg_id == tg_user.id)
            .values(**update_data)
        )
        await self.session.commit()

    async def _create_new_user(self, tg_user) -> User:
        """
        Создание нового пользователя
        """
        new_user = User(
            tg_id=tg_user.id,
            username=tg_user.username,
            first_name=tg_user.first_name,
            last_name=tg_user.last_name,
        )

        self.session.add(new_user)
        await self.session.commit()
        await self.session.refresh(new_user)

        print(f"✅ Новый пользователь создан: {new_user}")
        return new_user

    async def get_user_by_tg_id(self, tg_id: int) -> User | None:
        """
        Получение пользователя по Telegram ID
        """
        stmt = select(User).where(User.tg_id == tg_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()