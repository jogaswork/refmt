"""
Состояния конечного автомата (FSM) для всех сценариев бота.
"""
from aiogram.fsm.state import State, StatesGroup


class ApplicationForm(StatesGroup):
    """Заполнение анкеты пользователем."""
    waiting_for_answer = State()


class RejectReason(StatesGroup):
    """Ввод администратором причины отклонения заявки."""
    waiting_for_reason = State()


class GroupLinkSetup(StatesGroup):
    """Настройка ссылки на рабочую группу."""
    waiting_for_link = State()


class BroadcastForm(StatesGroup):
    """Создание рассылки для всех пользователей."""
    waiting_for_message = State()


class ProfileChatSetup(StatesGroup):
    """Настройка обязательного чата, доступ к которому нужен для вкладки «Профиль»."""
    waiting_for_chat_id = State()    # числовой ID чата или @username (для getChatMember)
    waiting_for_chat_link = State()  # ссылка-приглашение, показываемая пользователю


class ProfitAccrual(StatesGroup):
    """Начисление профита пользователю администратором."""
    waiting_for_user_id = State()
    waiting_for_amount = State()


class MentorForm(StatesGroup):
    """Добавление нового наставника администратором (по порядку: текст -> специализация -> условия)."""
    waiting_for_name = State()
    waiting_for_description = State()
    waiting_for_specialization = State()
    waiting_for_percent = State()
    waiting_for_profit_count = State()


class MentorEditText(StatesGroup):
    """Редактирование текста «О наставнике» у существующего наставника."""
    waiting_for_text = State()


class MentorEditSpecialization(StatesGroup):
    """Редактирование специализации у существующего наставника."""
    waiting_for_selection = State()


class MentorEditConditions(StatesGroup):
    """Редактирование условий сотрудничества (процент, количество профитов)."""
    waiting_for_percent = State()
    waiting_for_profit_count = State()
