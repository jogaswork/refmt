"""
Состояния конечного автомата (FSM) для всех сценариев бота.
"""
from aiogram.fsm.state import State, StatesGroup


class ApplicationForm(StatesGroup):
    waiting_for_answer = State()


class RejectReason(StatesGroup):
    waiting_for_reason = State()


class GroupLinkSetup(StatesGroup):
    waiting_for_link = State()


class BroadcastForm(StatesGroup):
    waiting_for_message = State()


class ProfileChatSetup(StatesGroup):
    waiting_for_chat_id = State()
    waiting_for_chat_link = State()


class ProfitAccrual(StatesGroup):
    waiting_for_user_id = State()
    waiting_for_amount = State()


class BanUser(StatesGroup):
    waiting_for_user_id = State()


class PersonalMessage(StatesGroup):
    waiting_for_user_id = State()
    waiting_for_message = State()


class MentorForm(StatesGroup):
    waiting_for_name = State()
    waiting_for_description = State()
    waiting_for_specialization = State()
    waiting_for_percent = State()
    waiting_for_profit_count = State()
    waiting_for_telegram_id = State()


class MentorEditText(StatesGroup):
    waiting_for_text = State()


class MentorEditSpecialization(StatesGroup):
    waiting_for_selection = State()


class MentorEditConditions(StatesGroup):
    waiting_for_percent = State()
    waiting_for_profit_count = State()


class MentorEditTelegramId(StatesGroup):
    waiting_for_telegram_id = State()


class NicknameChange(StatesGroup):
    """Смена кастомного ника в карточке профиля."""
    waiting_for_nickname = State()


class ChatLinkForm(StatesGroup):
    """Добавление ссылки в раздел «💬 Чаты» администратором."""
    waiting_for_title = State()
    waiting_for_url = State()
