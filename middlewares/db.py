from typing import Any, Awaitable, Callable, Dict
from aiogram import BaseMiddleware
from aiogram.types import Message, TelegramObject
from sqlalchemy.ext.asyncio import async_sessionmaker


class DataBaseSession(BaseMiddleware):
    def __init__(self, session_pool: async_sessionmaker):
        self.session_pool = session_pool

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        print(f"🔍 DataBaseSession: создание новой сессии")
        async with self.session_pool() as session:
            print(f"🔍 DataBaseSession: сессия создана {session}")
            data['session'] = session
            try:
                result = await handler(event, data)
                print(f"🔍 DataBaseSession: коммит сессии")
                await session.commit()
                print(f"🔍 DataBaseSession: коммит успешен")
                return result
            except Exception as e:
                print(f"🔍 DataBaseSession: ошибка, откат - {e}")
                await session.rollback()
                raise e
