"""
Все inline- и reply-клавиатуры бота.
"""
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.enums import ButtonStyle
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
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="✅Перейти к заполнению заявки!", callback_data="start_application")]
        ]
    )


def main_menu_reply() -> ReplyKeyboardMarkup:
    """Постоянное меню внизу экрана — одна кнопка «Меню»."""
    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(
                    text="Меню",
                    icon_custom_emoji_id="5886223731088431288"
                )
            ]
        ],
        resize_keyboard=True,
        is_persistent=True,
    )


def main_menu_inline(is_admin: bool = False) -> InlineKeyboardMarkup:
    """
    Инлайн-меню, которое приходит после эмодзи-заставки по кнопке «📋 Меню».
    """
    rows = [
        [
            InlineKeyboardButton(
                text="Профиль",
                callback_data="menu_profile",
                icon_custom_emoji_id="5258011929993026890",
                style=ButtonStyle.PRIMARY
            )
        ],
        [
            InlineKeyboardButton(
                text="Реферальная система",
                callback_data="menu_referral",
                icon_custom_emoji_id="5256143829672672750"
            )
        ],
        [
            InlineKeyboardButton(
                text="Ранги",
                callback_data="menu_ranks",
                icon_custom_emoji_id="5345892905103932200"
            )
        ],
        [
            InlineKeyboardButton(
                text="Информация",
                callback_data="menu_chats",
                icon_custom_emoji_id="5879501875341955281"
            )
        ],
    ]

    if is_admin:
        rows.append([
            InlineKeyboardButton(
                text="🛠 Админ-панель",
                callback_data="menu_admin_panel"
            )
        ])

    return InlineKeyboardMarkup(inline_keyboard=rows)


def back_to_menu_kb() -> InlineKeyboardMarkup:
    """Кнопка возврата в главное инлайн-меню (используется под разделом «Чаты»)."""
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="⬅️ Назад в меню", callback_data="menu_back")]]
    )


def join_chat_kb(chat_link: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="➡️ Вступить в чат", url=chat_link)]]
    )


def skip_reason_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="Пропустить", callback_data="skip_reason")]]
    )


# ---------------------------------------------------------------------------
# Наставники — пользовательские клавиатуры
# ---------------------------------------------------------------------------

def profile_kb() -> InlineKeyboardMarkup:
    """Кнопки под карточкой профиля — наставники, смена ника, назад в меню."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🎓 Наставники", callback_data="mentors_list")],
            [InlineKeyboardButton(text="✏️ Изменить ник", callback_data="profile_change_nick")],
            [InlineKeyboardButton(text="⬅️ Назад в меню", callback_data="menu_back")],
        ]
    )


def mentors_list_kb(mentors: list[dict]) -> InlineKeyboardMarkup:
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
# Раздел «💬 Чаты» (пользовательская сторона)
# ---------------------------------------------------------------------------

def chats_list_kb(chats: list[dict]) -> InlineKeyboardMarkup:
    """Каждый чат — отдельная кнопка-ссылка (Чат воркеров, Мануал и т.д.)."""
    rows = [[InlineKeyboardButton(text=c["title"], url=c["url"])] for c in chats]
    rows.append([InlineKeyboardButton(text="⬅️ Назад в меню", callback_data="menu_back")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


# ---------------------------------------------------------------------------
# Админ-клавиатуры
# ---------------------------------------------------------------------------

def application_decision_kb(app_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Принять", callback_data=f"accept_app:{app_id}"),
                InlineKeyboardButton(text="❌ Отклонить", callback_data=f"reject_app:{app_id}"),
            ]
        ]
    )


def admin_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="📋 Нерассмотренные заявки", callback_data="admin_pending"),
                InlineKeyboardButton(text="🔗 Настройка группы", callback_data="admin_group_setup"),
            ],
            [
                InlineKeyboardButton(text="📢 Рассылка", callback_data="admin_broadcast"),
                InlineKeyboardButton(text="👥 Пользователи (Рефералы)", callback_data="admin_users"),
            ],
            [
                InlineKeyboardButton(text="🔒 Чат для вкладки «Профиль»", callback_data="admin_profile_chat_setup"),
                InlineKeyboardButton(text="💰 Начислить профит", callback_data="admin_add_profit"),
            ],
            [
                InlineKeyboardButton(text="🎓 Наставники", callback_data="admin_mentors"),
                InlineKeyboardButton(text="💬 Чаты", callback_data="admin_chats"),
            ],
            [
                InlineKeyboardButton(text="🚫 Бан / разбан пользователя", callback_data="admin_ban_user"),
                InlineKeyboardButton(text="✉️ Сообщение одному пользователю", callback_data="admin_message_user"),
            ],
            [
                InlineKeyboardButton(text="📝 Логи бота", callback_data="admin_logs"),
            ],
        ]
    )


def admin_back_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="⬅️ Назад в меню", callback_data="admin_back")]]
    )


# ---------------------------------------------------------------------------
# Наставники — админ-клавиатуры
# ---------------------------------------------------------------------------

def admin_mentors_menu_kb(mentors: list[dict]) -> InlineKeyboardMarkup:
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
    if is_banned:
        action_button = InlineKeyboardButton(text="✅ Разбанить", callback_data=f"admin_unban_confirm:{user_id}")
    else:
        action_button = InlineKeyboardButton(text="🚫 Забанить", callback_data=f"admin_ban_confirm:{user_id}")
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [action_button],
            [InlineKeyboardButton(text="Отмена", callback_data="admin_back")],
        ]
    )


# ---------------------------------------------------------------------------
# Чаты — админ-клавиатуры
# ---------------------------------------------------------------------------

def admin_chats_menu_kb(chats: list[dict]) -> InlineKeyboardMarkup:
    """Список чатов в админке: удалить каждый + добавить новый."""
    rows = [
        [
            InlineKeyboardButton(text=c["title"], url=c["url"]),
            InlineKeyboardButton(text="🗑", callback_data=f"admin_chat_delete:{c['chat_link_id']}"),
        ]
        for c in chats
    ]
    rows.append([InlineKeyboardButton(text="➕ Добавить чат", callback_data="admin_chat_add")])
    rows.append([InlineKeyboardButton(text="⬅️ Назад в меню", callback_data="admin_back")])
    return InlineKeyboardMarkup(inline_keyboard=rows)
