"""
Middleware для логирования активности пользователей.

Подключается глобально в bot.py (dp.message.outer_middleware / dp.callback_query.outer_middleware),
поэтому автоматически охватывает ВСЕ хендлеры бота — и пользовательские, и админские —
без необходимости добавлять вызов логирования в каждый хендлер вручную.

Логи пишутся в таблицу `logs` (см. database.py) и доступны администратору
через раздел «📝 Логи бота» в /admin (см. handlers/admin.py).
"""
import logging
from typing import Any, Awaitable, Callable, Dict

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message

import database as db

logger = logging.getLogger(__name__)


class MessageLoggingMiddleware(BaseMiddleware):
    """Логирует каждое входящее текстовое сообщение или команду от пользователя."""

    async def __call__(
        self,
        handler: Callable[[Message, Dict[str, Any]], Awaitable[Any]],
        event: Message,
        data: Dict[str, Any],
    ) -> Any:
        try:
            # Для текстовых сообщений/команд берём текст, для остальных типов
            # контента (фото, документы и т.п.) — подпись или тип вложения.
            content = event.text or event.caption or f"[{event.content_type}]"
            await db.add_log(
                user_id=event.from_user.id if event.from_user else None,
                username=event.from_user.username if event.from_user else None,
                event_type="message",
                content=content,
            )
        except Exception:
            # Сбой логирования не должен мешать обработке самого сообщения.
            logger.exception("Не удалось записать лог сообщения")

        return await handler(event, data)


class CallbackLoggingMiddleware(BaseMiddleware):
    """Логирует каждое нажатие inline-кнопки (какой раздел/действие выбрал пользователь)."""

    async def __call__(
        self,
        handler: Callable[[CallbackQuery, Dict[str, Any]], Awaitable[Any]],
        event: CallbackQuery,
        data: Dict[str, Any],
    ) -> Any:
        try:
            await db.add_log(
                user_id=event.from_user.id if event.from_user else None,
                username=event.from_user.username if event.from_user else None,
                event_type="callback",
                content=event.data or "",
            )
        except Exception:
            logger.exception("Не удалось записать лог нажатия кнопки")

        return await handler(event, data)
