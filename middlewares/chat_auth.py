from typing import Any, Awaitable, Callable, Dict
from aiogram import BaseMiddleware
from aiogram.types import Message, TelegramObject, Update
from aiogram.enums import ChatMemberStatus
from aiogram.exceptions import TelegramAPIError
import logging

logger = logging.getLogger(__name__)


class ChatAuthMiddleware(BaseMiddleware):
    def __init__(self, admin_chat_id: str):
        self.admin_chat_id = admin_chat_id

    async def __call__(self, handler, event, data):

        # извлекаем Message
        if isinstance(event, Update):
            message = event.message
            if not message:
                return await handler(event, data)
            event_to_check = message
        else:
            return await handler(event, data)

        user_id = event_to_check.from_user.id

        # Проверка прав доступа
        try:
            member = await event_to_check.bot.get_chat_member(
                chat_id=self.admin_chat_id,
                user_id=user_id
            )
        except TelegramAPIError as e:
            logger.error(f"Ошибка доступа: {e}")
            await event_to_check.answer(
                "❌ Ошибка проверки доступа\n\n"
                "Убедитесь, что бот добавлен в группу и имеет права администратора."
            )
            return

        # Если не админ → блокируем
        if member.status not in (ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.CREATOR):
            await event_to_check.answer(
                "🚫 Доступ запрещён\n\n"
                "Этот бот доступен только администраторам группы."
            )
            return

        # Если всё нормально — запускаем следующий middleware/handler
        return await handler(event, data)
