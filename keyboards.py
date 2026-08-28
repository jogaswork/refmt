"""
Все inline- и reply-клавиатуры бота.
"""

from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
)

from config import MENTOR_SPECIALIZATIONS

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
# Наставники — пользовательские клавиатуры
# ---------------------------------------------------------------------------


def profile_kb() -> InlineKeyboardMarkup:
    """Кнопка под текстом вкладки «Профиль» — переход к наставникам."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🎓 Наставники", callback_data="mentors_list")]
        ]
    )


def mentors_list_kb(mentors: list[dict]) -> InlineKeyboardMarkup:
    """Список наставников (по кнопке на каждого) + навигация."""
    rows = [
        [InlineKeyboardButton(text=m["name"], callback_data=f"mentor_view:{m['mentor_id']}")]
        for m in mentors
    ]
    rows.append(
        [
            InlineKeyboardButton(text="⬅️ Назад", callback_data="mentors_back_to_profile"),
            InlineKeyboardButton(text="🏠 Домой", callback_data="mentors_home"),
        ]
    )
    return InlineKeyboardMarkup(inline_keyboard=rows)


def mentor_card_kb(mentor_id: int) -> InlineKeyboardMarkup:
    """Карточка конкретного наставника: подать заявку + навигация."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="✅ Подать заявку", callback_data=f"mentor_apply:{mentor_id}")],
            [
                InlineKeyboardButton(text="⬅️ Назад", callback_data="mentors_list"),
                InlineKeyboardButton(text="🏠 Домой", callback_data="mentors_home"),
            ],
        ]
    )


def mentor_spec_toggle_kb(selected: set[str]) -> InlineKeyboardMarkup:
    """
    Клавиатура множественного выбора специализации наставника (для админки).
    Выбранные пункты помечаются ✅. Используется и при создании, и при редактировании.
    """
    rows = [
        [
            InlineKeyboardButton(
                text=f"{'✅ ' if key in selected else ''}{button_label}",
                callback_data=f"mentor_spec_toggle:{key}",
            )
        ]
        for key, button_label, _ in MENTOR_SPECIALIZATIONS
    ]
    rows.append([InlineKeyboardButton(text="Готово ➡️", callback_data="mentor_spec_done")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


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
            [InlineKeyboardButton(text="🔗 Настройка группы", callback_data="admin_group_setup")],
            [InlineKeyboardButton(text="📢 Рассылка", callback_data="admin_broadcast")],
            [InlineKeyboardButton(text="👥 Пользователи (Рефералы)", callback_data="admin_users")],
            [InlineKeyboardButton(text="🔒 Чат для вкладки «Профиль»", callback_data="admin_profile_chat_setup")],
            [InlineKeyboardButton(text="💰 Начислить профит", callback_data="admin_add_profit")],
            [InlineKeyboardButton(text="🧹 Сбросить профит", callback_data="admin_reset_profit")],
            [InlineKeyboardButton(text="🎓 Наставники", callback_data="admin_mentors")],
            [InlineKeyboardButton(text="🚫 Бан / разбан пользователя", callback_data="admin_ban_user")],
            [InlineKeyboardButton(text="✉️ Сообщение одному пользователю", callback_data="admin_message_user")],
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


# ---------------------------------------------------------------------------
# Наставники — админ-клавиатуры
# ---------------------------------------------------------------------------


def admin_mentors_menu_kb(mentors: list[dict]) -> InlineKeyboardMarkup:
    """Список наставников в админке: редактировать/удалить каждого + добавить нового."""
    rows = [
        [
            InlineKeyboardButton(text=f"✏️ {m['name']}", callback_data=f"admin_mentor_edit:{m['mentor_id']}"),
            InlineKeyboardButton(text="🗑", callback_data=f"admin_mentor_delete:{m['mentor_id']}"),
        ]
        for m in mentors
    ]
    rows.append([InlineKeyboardButton(text="➕ Добавить наставника", callback_data="admin_mentor_add")])
    rows.append([InlineKeyboardButton(text="⬅️ Назад в меню", callback_data="admin_back")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def admin_mentor_edit_menu_kb(mentor_id: int) -> InlineKeyboardMarkup:
    """Меню редактирования конкретного наставника."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="✏️ Изменить текст", callback_data=f"admin_mentor_edit_text:{mentor_id}")],
            [InlineKeyboardButton(text="🏷 Изменить специализацию", callback_data=f"admin_mentor_edit_spec:{mentor_id}")],
            [InlineKeyboardButton(text="💰 Изменить условия", callback_data=f"admin_mentor_edit_conditions:{mentor_id}")],
            [InlineKeyboardButton(text="🗑 Удалить наставника", callback_data=f"admin_mentor_delete:{mentor_id}")],
            [InlineKeyboardButton(text="⬅️ Назад к списку", callback_data="admin_mentors")],
        ]
    )


def admin_mentor_delete_confirm_kb(mentor_id: int) -> InlineKeyboardMarkup:
    """Подтверждение удаления наставника."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="❌ Да, удалить", callback_data=f"admin_mentor_delete_confirm:{mentor_id}"),
                InlineKeyboardButton(text="Отмена", callback_data=f"admin_mentor_edit:{mentor_id}"),
            ]
        ]
    )


# ---------------------------------------------------------------------------
# Бан пользователей — админ-клавиатура
# ---------------------------------------------------------------------------


def admin_ban_action_kb(user_id: int, is_banned: bool) -> InlineKeyboardMarkup:
    """
    Кнопка действия над конкретным пользователем: показывает «Забанить», если
    он сейчас не забанен, и «Разбанить» — если уже забанен (плюс отмена).
    """
    if is_banned:
        action_button = InlineKeyboardButton(
            text="✅ Разбанить", callback_data=f"admin_unban_confirm:{user_id}"
        )
    else:
        action_button = InlineKeyboardButton(
            text="🚫 Забанить", callback_data=f"admin_ban_confirm:{user_id}"
        )
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [action_button],
            [InlineKeyboardButton(text="Отмена", callback_data="admin_back")],
        ]
    )
