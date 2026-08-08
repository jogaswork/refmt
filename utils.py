"""
Вспомогательные функции общего назначения:
- проверка подписки пользователя на обязательный чат (для вкладки «Профиль»);
- форматирование текста профиля пользователя.
"""
import datetime
import logging
from typing import Any, Optional

from aiogram import Bot
from aiogram.enums import ChatMemberStatus

logger = logging.getLogger(__name__)

# Статусы участника чата, которые считаем «пользователь состоит в чате».
# 'left' (вышел) и 'kicked' (исключён) сюда не входят.
_ACTIVE_MEMBER_STATUSES = {
    ChatMemberStatus.CREATOR,
    ChatMemberStatus.ADMINISTRATOR,
    ChatMemberStatus.MEMBER,
    ChatMemberStatus.RESTRICTED,
}


async def is_chat_member(bot: Bot, chat_id: str, user_id: int) -> bool:
    """
    Проверяет через Telegram API (getChatMember), состоит ли пользователь в чате.

    chat_id — значение, заданное администратором через /admin (см. handlers/admin.py):
    это может быть числовой ID чата (например, "-1001234567890") или
    @username публичного чата.

    ВАЖНО: чтобы проверка работала, бот должен быть добавлен в этот чат
    (рекомендуется — администратором чата), иначе Telegram API вернёт ошибку
    доступа, и функция вернёт False (доступ будет считаться непройденным).
    """
    if not chat_id:
        # Обязательный чат не настроен админом — проверять нечего.
        return False

    try:
        member = await bot.get_chat_member(chat_id=chat_id, user_id=user_id)
        return member.status in _ACTIVE_MEMBER_STATUSES
    except Exception as error:
        # Сюда попадают, например, ситуации «бот не состоит в чате» или
        # «пользователь никогда не писал боту» — в обоих случаях безопаснее
        # считать проверку не пройденной, чем падать с исключением.
        logger.warning(
            "Не удалось проверить членство user_id=%s в chat_id=%s: %s",
            user_id, chat_id, error,
        )
        return False


def _parse_joined_at(raw: Optional[str]) -> Optional[datetime.datetime]:
    """Парсит дату регистрации, сохранённую в БД в формате ISO 8601."""
    if not raw:
        return None
    try:
        return datetime.datetime.fromisoformat(raw)
    except ValueError:
        return None


def days_in_bot(joined_at_raw: Optional[str]) -> int:
    """Считает, сколько полных дней прошло с момента регистрации пользователя."""
    joined_at = _parse_joined_at(joined_at_raw)
    if joined_at is None:
        return 0
    delta = datetime.datetime.utcnow() - joined_at
    return max(delta.days, 0)


def format_rubles(amount: float) -> str:
    """Форматирует сумму в рублях с разделением разрядов пробелом: 12345 -> '12 345'."""
    return f"{amount:,.0f}".replace(",", " ")


def format_profile(user: dict[str, Any], referrals_count: int) -> str:
    """Собирает текст сообщения для вкладки «Профиль»."""
    profits = user.get("profits") or 0
    joined_at_raw = user.get("joined_at")
    days = days_in_bot(joined_at_raw)

    joined_display = "неизвестно"
    parsed = _parse_joined_at(joined_at_raw)
    if parsed is not None:
        joined_display = parsed.strftime("%d.%m.%Y")

    return (
        "👤 <b>Ваш профиль</b>\n\n"
        f"💰 Сумма профитов: <b>{format_rubles(profits)} ₽</b>\n"
        f"👥 Привлечено рефералов: <b>{referrals_count}</b>\n"
        f"📅 Вы с нами: <b>{days}</b> дн. (дата регистрации: {joined_display})"
    )
