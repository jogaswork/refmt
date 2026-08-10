"""
Middleware для сбора логов действий пользователей.
Логирует каждое входящее текстовое сообщение и каждое нажатие inline-кнопки,
чтобы админ мог посмотреть их в разделе «Логи бота».
"""

from typing import Any, Awaitable, Callable, Dict

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message, TelegramObject

import database as db


class LoggingMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        try:
            if isinstance(event, Message):
                content = event.text or event.caption or f"[{event.content_type}]"
                await db.add_log(
                    user_id=event.from_user.id if event.from_user else None,
                    username=event.from_user.username if event.from_user else None,
                    event_type="message",
                    content=content,
                )
            elif isinstance(event, CallbackQuery):
                await db.add_log(
                    user_id=event.from_user.id if event.from_user else None,
                    username=event.from_user.username if event.from_user else None,
                    event_type="callback",
                    content=event.data,
                )
        except Exception:
            # Логирование не должно ронять обработку основного события бота
            pass

        return await handler(event, data)
