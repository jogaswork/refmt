"""
Middleware для сбора логов действий пользователей и для бана.

- LoggingMiddleware: логирует каждое входящее текстовое сообщение и каждое
  нажатие inline-кнопки, чтобы админ мог посмотреть их в разделе «Логи бота».
- BanMiddleware: блокирует любое взаимодействие с ботом для забаненных
  пользователей (см. /admin -> «🚫 Бан / разбан пользователя»).
"""

from typing import Any, Awaitable, Callable, Dict

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, InlineQuery, Message, TelegramObject

import database as db
from config import ADMIN_IDS


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


class BanMiddleware(BaseMiddleware):
    """
    Полностью блокирует обработку сообщений, нажатий кнопок и инлайн-запросов
    от забаненных пользователей — их апдейты просто не доходят до хендлеров.
    Администраторы (ADMIN_IDS) никогда не блокируются этой проверкой, даже
    если в базе у них случайно выставлен флаг banned.
    """

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        user = getattr(event, "from_user", None)

        if user is not None and user.id not in ADMIN_IDS:
            try:
                banned = await db.is_user_banned(user.id)
            except Exception:
                banned = False

            if banned:
                try:
                    if isinstance(event, Message):
                        await event.answer("🚫 Вы заблокированы в этом боте.")
                    elif isinstance(event, CallbackQuery):
                        await event.answer("🚫 Вы заблокированы в этом боте.", show_alert=True)
                    elif isinstance(event, InlineQuery):
                        await event.answer([], cache_time=1)
                except Exception:
                    pass
                return  # не пропускаем событие дальше к хендлерам

        return await handler(event, data)
