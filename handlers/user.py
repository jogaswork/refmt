"""
Обработчики пользовательского сценария:
/start -> подача заявки -> уведомление админов; реферальная система.
"""
from html import escape as html_escape
from pathlib import Path

from aiogram import Bot, F, Router
from aiogram.filters import CommandObject, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, FSInputFile, Message

import database as db
import keyboards as kb
from config import ADMIN_IDS
from states import ApplicationForm
from utils import format_profile, is_chat_member

router = Router(name="user")

# Абсолютный путь к папке с картинками — не зависит от того, откуда запущен bot.py
IMAGES_DIR = Path(__file__).resolve().parent.parent / "images"

# ID премиум-эмодзи, показывается вместо 🎉 в уведомлении рефовода о новом реферале.
# Fallback-символ внутри тега используется у тех, кому Premium недоступен.
NEW_REFERRAL_EMOJI_ID = "5458824569026532353"

ANKET_TEXT = (
    "🚀 Перед тем, как начать зарабатывать миллионы, нужно ответить на несколько вопросов!\n\n"
    "1. Опишите свой опыт работы в данной сфере? (Где раньше воркали, на каких площадках, сколько заработали)\n"
    "2. Сколько времени готовы уделять работе?\n"
    "3. Откуда узнали о нас? (Ссылка на друга или бота, или тикток)\n\n"
    "👁️ Ответ писать ОДНИМ сообщением в ОТВЕТ на это, заявки не по форме будут автоматически отклоняться!"
)


@router.message(CommandStart())
async def cmd_start(message: Message, command: CommandObject, state: FSMContext, bot: Bot) -> None:
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

    is_new_user = not await db.user_exists(user_id)
    if is_new_user:
        await db.add_user(user_id, username, first_name, referrer_id)

    # Уведомляем рефовода о новом реферале — только если пользователь
    # регистрируется впервые (иначе один и тот же реферал мог бы
    # "нафармить" уведомления повторными /start).
    if is_new_user and referrer_id is not None:
        who = html_escape(f"@{username}" if username else first_name)
        try:
            await bot.send_message(
                referrer_id,
                f'<tg-emoji emoji-id="{NEW_REFERRAL_EMOJI_ID}">🎉</tg-emoji> '
                f"У вас новый реферал: {who}!\n"
                "Как только он выйдет в первый профит, вам начислится 10%.",
            )
        except Exception:
            # Рефовод мог не запускать бота / заблокировать его — пропускаем
            pass

    await message.answer(
        f"Привет, {html_escape(first_name)}! Добро пожаловать в команду 🚀",
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

    # Путь к картинке — абсолютный, не зависит от рабочей директории процесса
    photo_path = IMAGES_DIR / "111.jpg"

    try:
        await message.answer_photo(photo=FSInputFile(photo_path), caption=text)
    except Exception:
        # Картинка могла быть перемещена/удалена — не роняем хендлер,
        # отправляем хотя бы текст со ссылкой.
        await message.answer(text)


@router.message(F.text == "👤 Профиль")
async def show_profile(message: Message, bot: Bot) -> None:
    """
    Вкладка «Профиль»: сумма профитов, количество рефералов, сколько дней в боте.

    Доступна только пользователям, состоящим в обязательном рабочем чате
    (chat_id настраивается администратором через /admin -> «🔒 Чат для вкладки
    «Профиль»»). Если чат не настроен админом (пустое значение) — проверка
    пропускается и профиль доступен всем.
    """
    user_id = message.from_user.id

    required_chat_id = await db.get_setting("required_chat_id", "")
    required_chat_link = await db.get_setting("required_chat_link", "")

    if required_chat_id and not await is_chat_member(bot, required_chat_id, user_id):
        # Пользователь не состоит в обязательном чате — доступ к профилю закрыт.
        warning_text = (
            "🔒 Вкладка «Профиль» доступна только участникам нашего рабочего чата.\n\n"
            "Пожалуйста, вступите в чат по кнопке ниже и попробуйте снова 👇"
        )
        if required_chat_link:
            await message.answer(warning_text, reply_markup=kb.join_chat_kb(required_chat_link))
        else:
            # Ссылка ещё не настроена админом — предупреждаем без кнопки.
            await message.answer(
                warning_text + "\n\n(Ссылка на чат пока не настроена администратором.)"
            )
        return

    # Пользователь прошёл проверку подписки (или проверка отключена) — показываем профиль.
    user = await db.get_user(user_id)
    if user is None:
        # На случай, если запись о пользователе почему-то отсутствует в БД —
        # создаём её "на лету", чтобы не ронять хендлер.
        await db.add_user(user_id, message.from_user.username, message.from_user.first_name, None)
        user = await db.get_user(user_id)

    referrals_count = await db.get_referrals_count(user_id)
    await message.answer(format_profile(user, referrals_count))
