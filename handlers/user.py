"""
Обработчики пользовательского сценария:
/start -> подача заявки -> уведомление админов; реферальная система.
"""
from aiogram.types import FSInputFile
from aiogram import Bot, F, Router
from aiogram.filters import CommandObject, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

import database as db
import keyboards as kb
from config import ADMIN_IDS
from states import ApplicationForm

router = Router(name="user")

ANKET_TEXT = (
    "🚀 Перед тем, как начать зарабатывать миллионы, нужно ответить на несколько вопросов!\n\n"
    "1. Опишите свой опыт работы в данной сфере? (Где раньше воркали, на каких площадках, сколько заработали)\n"
    "2. Сколько времени готовы уделять работе?\n"
    "3. Откуда узнали о нас? (Ссылка на друга или бота, или тикток)\n\n"
    "👁️ Ответ писать ОДНИМ сообщением в ОТВЕТ на это, заявки не по форме будут автоматически отклоняться!"
)


@router.message(CommandStart())
async def cmd_start(message: Message, command: CommandObject, state: FSMContext) -> None:
    """Обработка команды /start, в т.ч. с реферальным payload вида /start 123456."""
    await state.clear()

    user_id = message.from_user.id
    username = message.from_user.username
    first_name = message.from_user.first_name or "друг"

    referrer_id = None
    if command.args:
        payload = command.args.strip()
        if payload.isdigit():
            candidate = int(payload)
            if candidate != user_id:
                referrer_id = candidate

    if not await db.user_exists(user_id):
        await db.add_user(user_id, username, first_name, referrer_id)

    await message.answer(
        f"Привет, {first_name}! Добро пожаловать в команду 🚀",
        reply_markup=kb.start_application_inline(),
    )
    # Отдельным сообщением выставляем постоянное меню с реферальной системой
    await message.answer(
        "Используй меню ниже, чтобы перейти в реферальную систему в любой момент 👇",
        reply_markup=kb.main_menu_reply(),
    )


@router.callback_query(F.data == "start_application")
async def start_application(callback: CallbackQuery, state: FSMContext) -> None:
    """Пользователь нажал «Перейти к заполнению заявки»."""
    await callback.message.answer(ANKET_TEXT)
    await state.set_state(ApplicationForm.waiting_for_answer)
    await callback.answer()


@router.message(ApplicationForm.waiting_for_answer)
async def process_application(message: Message, state: FSMContext, bot: Bot) -> None:
    """Приём ответа на анкету одним сообщением и рассылка админам."""
    answer_text = message.text or message.caption

    if not answer_text:
        await message.answer(
            "Пожалуйста, ответьте на анкету текстовым сообщением 🙏"
        )
        return

    app_id = await db.create_application(
        user_id=message.from_user.id,
        username=message.from_user.username,
        text=answer_text,
    )
    await state.clear()

    await message.answer("Ваша заявка успешно отправлена! Ожидайте решения администрации ⏳")

    admin_text = (
        f"📋 Новая заявка #{app_id}\n\n"
        f"ID пользователя: {message.from_user.id}\n"
        f"Username: @{message.from_user.username or 'отсутствует'}\n\n"
        f"Анкета:\n{answer_text}"
    )
    decision_kb = kb.application_decision_kb(app_id)

    for admin_id in ADMIN_IDS:
        try:
            await bot.send_message(admin_id, admin_text, reply_markup=decision_kb)
        except Exception:
            # Админ мог не запускать бота / заблокировать его — пропускаем
            continue


@router.message(F.text == "🔗 Реферальная система")
async def referral_system(message: Message, bot: Bot) -> None:
    """Показ реферальной ссылки пользователя."""
    me = await bot.get_me()
    ref_link = f"https://t.me/{me.username}?start={message.from_user.id}"

    text = (
        f"Ваша реферальная ссылка: \n\n{ref_link}\n\n"
        "Вы получаете 10% с первого профита реферала. Выплаты осуществляются администратором.\n"
        "Для получения выплаты отпишите: @manzi_nx или @jogas_wor"
    )

    # Путь к вашей картинке
    photo = FSInputFile("images/111.jpg")

    # Отправка фото с текстом
    await message.answer_photo(
        photo=photo,
        caption=text
    )  # <-- Скобка должна быть с отступом 4 пробела!
