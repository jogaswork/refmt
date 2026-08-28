"""
Вспомогательные функции общего назначения:
- проверка подписки пользователя на обязательный чат (для вкладки «Профиль»);
- форматирование текста профиля пользователя.
"""
import datetime
import logging
from html import escape as html_escape
from typing import Any, Optional

from aiogram import Bot
from aiogram.enums import ChatMemberStatus

from config import MENTOR_SPECIALIZATIONS

logger = logging.getLogger(__name__)

_SPEC_LABELS: dict[str, str] = {key: display_label for key, _, display_label in MENTOR_SPECIALIZATIONS}
# «Плоская» версия — обычный юникод-эмодзи без HTML/тегов премиум-эмодзи.
# Нужна там, где HTML не поддерживается: description инлайн-результатов,
# текст кнопок и т.п. (см. specialization_keys_to_plain_labels).
_SPEC_PLAIN_LABELS: dict[str, str] = {key: button_label for key, button_label, _ in MENTOR_SPECIALIZATIONS}

# Через сколько секунд после отклонения заявки можно подать новую (антиспам).
APPLICATION_COOLDOWN_SECONDS = 60

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


def application_eligibility(latest_application: Optional[dict[str, Any]]) -> tuple[bool, Optional[str]]:
    """
    Определяет, может ли пользователь подать новую заявку прямо сейчас.

    Возвращает (can_apply, blocking_message):
    - если заявка уже принята — подавать больше нельзя (навсегда);
    - если заявка на рассмотрении — подавать нельзя, пока не решат текущую;
    - если заявка отклонена — подавать нельзя ближайшую минуту после отказа (антиспам),
      дальше — можно;
    - если заявок ещё не было — можно.
    """
    if latest_application is None:
        return True, None

    status = latest_application.get("status")

    if status == "accepted":
        return False, "🎉 Ваша заявка уже принята, вы в команде! Повторно подавать не нужно."

    if status == "pending":
        return False, "⏳ Ваша заявка уже на рассмотрении. Дождитесь решения администрации."

    if status == "rejected":
        decided_raw = latest_application.get("decided_at") or latest_application.get("created_at")
        decided_at = _parse_joined_at(decided_raw)
        if decided_at is not None:
            elapsed = (datetime.datetime.utcnow() - decided_at).total_seconds()
            remaining = APPLICATION_COOLDOWN_SECONDS - elapsed
            if remaining > 0:
                wait_seconds = int(remaining) + 1
                return False, f"⏳ Вы сможете подать заявку заново через {wait_seconds} сек."
        return True, None

    # Неизвестный/прочий статус — по умолчанию не блокируем.
    return True, None


def format_profile(user: dict[str, Any], referrals_count: int) -> str:
    """Собирает текст сообщения для вкладки «Профиль»."""
    profits = user.get("profit") or 0
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


def specialization_keys_to_labels(raw: Optional[str]) -> list[str]:
    """Превращает 'rest,trade' из БД в список подписей вида ['🏖 Отдых', '📈 Трейд'] (с HTML/премиум-эмодзи)."""
    if not raw:
        return []
    keys = [key.strip() for key in raw.split(",") if key.strip()]
    return [_SPEC_LABELS.get(key, key) for key in keys]


def specialization_keys_to_plain_labels(raw: Optional[str]) -> list[str]:
    """То же самое, но без HTML — обычный эмодзи вместо тега премиум-эмодзи.
    Использовать там, где HTML не поддерживается (например, поля инлайн-результатов)."""
    if not raw:
        return []
    keys = [key.strip() for key in raw.split(",") if key.strip()]
    return [_SPEC_PLAIN_LABELS.get(key, key) for key in keys]


def format_mentor_card(mentor: dict[str, Any]) -> str:
    """Собирает текст карточки наставника (профиль наставника с условиями сотрудничества)."""
    spec_labels = specialization_keys_to_labels(mentor.get("specialization"))
    spec_display = " • ".join(spec_labels) if spec_labels else "не указана"

    percent = mentor.get("profit_percent") or 0
    count = mentor.get("profit_count") or 0
    description = mentor.get("description") or "—"
    name = mentor.get("name") or "—"

    return (
        "👤 <b>Наставник</b>\n\n"
        f"👤 Профиль: <b>{html_escape(str(name))}</b>\n\n"
        f"ℹ️ О наставнике:\n{html_escape(str(description))}\n\n"
        f"🏷 Специализация:\n{spec_display}\n\n"
        "💰 Условия сотрудничества:\n"
        f"• Процент от профита: {percent:g}%\n"
        f"• Количество профитов: {int(count)}"
    )
