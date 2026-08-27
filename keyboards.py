"""
Все inline- и reply-клавиатуры бота.
"""
from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
)


# ---------------------------------------------------------------------------
# Пользовательские клавиатуры
# ---------------------------------------------------------------------------

def start_application_inline() -> InlineKeyboardMarkup:
    """Кнопка под приветственным сообщением."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="✅Перейти к заполнению заявки!", callback_data="start_application")]
        ]
    )


def main_menu_reply() -> ReplyKeyboardMarkup:
    """Постоянное меню внизу экрана."""
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🔗 Реферальная система")],
            [KeyboardButton(text="👤 Профиль")],
        ],
        resize_keyboard=True,
        is_persistent=True,
    )


def join_chat_kb(chat_link: str) -> InlineKeyboardMarkup:
    """
    Кнопка-ссылка на вступление в обязательный чат.
    Показывается, если пользователь нажал «Профиль», но не состоит в чате
    (см. handlers/user.py -> show_profile).
    """
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="➡️ Вступить в чат", url=chat_link)]
        ]
    )


def skip_reason_kb() -> InlineKeyboardMarkup:
    """Клавиатура «Пропустить» при вводе причины отказа."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Пропустить", callback_data="skip_reason")]
        ]
    )


# ---------------------------------------------------------------------------
# Админ-клавиатуры
# ---------------------------------------------------------------------------

def application_decision_kb(app_id: int) -> InlineKeyboardMarkup:
    """Кнопки принять/отклонить под конкретной заявкой."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Принять", callback_data=f"accept_app:{app_id}"),
                InlineKeyboardButton(text="❌ Отклонить", callback_data=f"reject_app:{app_id}"),
            ]
        ]
    )


def admin_menu() -> InlineKeyboardMarkup:
    """Главное меню админ-панели."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📋 Нерассмотренные заявки", callback_data="admin_pending")],
            [InlineKeyboardButton(text="🎓 Наставники", callback_data="admin_mentors")],
            [InlineKeyboardButton(text="🔗 Настройка группы", callback_data="admin_group_setup")],
            [InlineKeyboardButton(text="📢 Рассылка", callback_data="admin_broadcast")],
            [InlineKeyboardButton(text="👥 Пользователи (Рефералы)", callback_data="admin_users")],
            [InlineKeyboardButton(text="🔒 Чат для вкладки «Профиль»", callback_data="admin_profile_chat_setup")],
            [InlineKeyboardButton(text="💰 Начислить профит", callback_data="admin_add_profit")],
            [InlineKeyboardButton(text="📝 Логи бота", callback_data="admin_logs")],
        ]
    )


def admin_back_kb() -> InlineKeyboardMarkup:
    """Кнопка возврата в главное меню админки."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="⬅️ Назад в меню", callback_data="admin_back")]
        ]
    )
