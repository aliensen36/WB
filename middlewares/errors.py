# middlewares/errors.py
from typing import Any, Awaitable, Callable, Dict
from aiogram import BaseMiddleware
from aiogram.types import Message, TelegramObject, Update
import logging

logger = logging.getLogger(__name__)


class ErrorMiddleware(BaseMiddleware):
    async def __call__(
            self,
            handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
            event: TelegramObject,
            data: Dict[str, Any],
    ) -> Any:
        try:
            result = await handler(event, data)
            return result
        except Exception as e:
            # Логируем ошибку
            logger.error(f"💥 Необработанная ошибка: {e}", exc_info=True)

            # Получаем объект сообщения для ответа
            message = None
            if isinstance(event, Update):
                message = event.message or event.callback_query
            elif isinstance(event, Message):
                message = event

            # Отправляем сообщение пользователю
            if message and hasattr(message, 'answer'):
                try:
                    # Разные сообщения для разных типов ошибок
                    if "get_account_management_keyboard" in str(e):
                        error_text = "❌ Ошибка в формировании меню. Разработчик уведомлен."
                    else:
                        error_text = "❌ Произошла внутренняя ошибка. Разработчик уже уведомлен."

                    await message.answer(error_text)
                except Exception:
                    pass

            return
