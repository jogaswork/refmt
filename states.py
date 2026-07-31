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
