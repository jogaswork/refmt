"""
Обработчики пользовательского сценария:
/start -> подача заявки -> уведомление админов; реферальная система; меню.
"""

import asyncio
from html import escape as html_escape
from pathlib import Path
from typing import Optional

from aiogram import Bot, F, Router
from aiogram.filters import CommandObject, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import (
    CallbackQuery,
    FSInputFile,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    InlineQuery,
    InlineQueryResultArticle,
    InputTextMessageContent,
    Message,
)

import database as db
import keyboards as kb
from config import ADMIN_IDS
from states import ApplicationForm
from utils import (
    application_eligibility,
    format_mentor_card,
    format_profile,
    is_chat_member,
    specialization_keys_to_plain_labels,
)

router = Router(name="user")

# Абсолютный путь к папке с картинками — не зависит от того, откуда запущен bot.py
IMAGES_DIR = Path(__file__).resolve().parent.parent / "images"

# ID премиум-эмодзи, показывается вместо 🎉 в уведомлении рефовода о новом реферале.
# Fallback-символ внутри тега используется у тех, кому Premium недоступен.
NEW_REFERRAL_EMOJI_ID = "5458824569026532353"

# ID премиум-эмодзи, показывается отдельным сообщением перед инлайн-меню
# (кнопка «📋 Меню») — сначала прилетает эмодзи, через паузу — само меню.
MENU_EMOJI_ID = "5893057118545646106"
MENU_EMOJI_DELAY = 0.8  # секунды между эмодзи и меню

# Префикс диплинка для прикрепления к наставнику: t.me/<bot>?start=mentor_<id>
# Используется и в inline-режиме (см. inline_query_handler), и как обычная /start-ссылка.
MENTOR_DEEPLINK_PREFIX = "mentor_"

ANKET_TEXT = (
    "🚀 Перед тем, как начать зарабатывать миллионы, нужно ответить на несколько вопросов!\n\n"
    "1. Опишите свой опыт работы в данной сфере? (Где раньше воркали, на каких площадках, сколько заработали)\n"
    "2. Сколько времени готовы уделять работе?\n"
    "3. Откуда узнали о нас? (Ссылка на друга или бота, или тикток)\n\n"
    "👁️ Ответ писать ОДНИМ сообщением в ОТВЕТ на это, заявки не по форме будут автоматически отклоняться!"
)


async def _attach_user_to_mentor(
    bot: Bot,
    user_id: int,
    username: str | None,
    first_name: str | None,
    mentor_id: int,
) -> Optional[dict]:
    """
    Закрепляет пользователя за наставником: создаёт запись пользователя при
    необходимости, пишет mentor_id и уведомляет админов.
    Возвращает словарь наставника (или None, если такого наставника не существует).
    Используется и кнопкой «✅ Подать заявку», и диплинком /start mentor_<id>
    (в т.ч. из инлайн-режима).
    """
    mentor = await db.get_mentor(mentor_id)
    if not mentor:
        return None

    if not await db.user_exists(user_id):
        await db.add_user(user_id, username, first_name, None)

    await db.set_user_mentor(user_id, mentor_id)

    who = html_escape(f"@{username}" if username else (first_name or str(user_id)))
    admin_text = (
        f"🎓 Пользователь {who} (ID: {user_id}) закрепился за наставником "
        f"«{html_escape(mentor['name'])}»."
    )
    for admin_id in ADMIN_IDS:
        try:
            await bot.send_message(admin_id, admin_text)
        except Exception:
            # Админ мог не запускать бота / заблокировать его — пропускаем
            continue

    return mentor


@router.message(CommandStart())
async def cmd_start(message: Message, command: CommandObject, state: FSMContext, bot: Bot) -> None:
    """
    Обработка команды /start, в т.ч. с payload:
    - числовой payload вида /start 123456 — реферальная ссылка;
    - payload вида /start mentor_5 — диплинк на прикрепление к наставнику
      (в т.ч. присланный через инлайн-режим, см. inline_query_handler).
    """
    await state.clear()
    user_id = message.from_user.id
    username = message.from_user.username
    first_name = message.from_user.first_name or "друг"

    referrer_id = None
    mentor_deeplink_id: Optional[int] = None

    if command.args:
        payload = command.args.strip()
        if payload.startswith(MENTOR_DEEPLINK_PREFIX):
            candidate = payload[len(MENTOR_DEEPLINK_PREFIX):]
            if candidate.isdigit():
                mentor_deeplink_id = int(candidate)
        elif payload.isdigit():
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

    # Если заявка уже принята — кнопку «Подать заявку» больше не показываем,
    # чтобы не провоцировать повторную подачу (см. application_eligibility).
    latest_app = await db.get_latest_application(user_id)
    already_accepted = latest_app is not None and latest_app.get("status") == "accepted"

    if already_accepted:
        await message.answer(
            f"С возвращением, {html_escape(first_name)}! Вы уже в команде 🎉\n"
            "Повторная подача заявки не требуется."
        )
    else:
        await message.answer(
            f"Привет, {html_escape(first_name)}! Добро пожаловать в команду 🚀",
            reply_markup=kb.start_application_inline(),
        )

    # Отдельным сообщением выставляем постоянное меню (кнопка «📋 Меню» внизу экрана)
    await message.answer(
        "Используй кнопку «📋 Меню» ниже, чтобы в любой момент перейти в профиль, "
        "реферальную систему или чаты 👇",
        reply_markup=kb.main_menu_reply(),
    )

    # Пользователь перешёл по диплинку наставника (обычная ссылка или инлайн-режим) —
    # закрепляем его сразу, тем же способом, что и кнопка «✅ Подать заявку».
    if mentor_deeplink_id is not None:
        mentor = await _attach_user_to_mentor(bot, user_id, username, first_name, mentor_deeplink_id)
        if mentor:
            await message.answer(
                f"✅ Вы закрепились за наставником <b>{html_escape(mentor['name'])}</b>!\n"
                "Он свяжется с вами в ближайшее время."
            )
        else:
            await message.answer("Этот наставник больше недоступен.")


@router.callback_query(F.data == "start_application")
async def start_application(callback: CallbackQuery, state: FSMContext) -> None:
    """
    Пользователь нажал «Перейти к заполнению заявки».
    Реальная проверка (можно ли подавать заявку прямо сейчас) — здесь, а не
    только в /start, потому что кнопка могла остаться в старом сообщении:
    - заявка уже принята -> подавать больше не нужно;
    - заявка на рассмотрении -> ждём решения;
    - заявка отклонена меньше минуты назад -> антиспам-пауза (см. application_eligibility).
    """
    user_id = callback.from_user.id
    latest_app = await db.get_latest_application(user_id)
    can_apply, blocking_message = application_eligibility(latest_app)

    if not can_apply:
        await callback.answer(blocking_message, show_alert=True)
        return

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


# ---------------------------------------------------------------------------
# Меню: «📋 Меню» -> премиум-эмодзи -> инлайн-меню (Профиль / Реф.система / Чаты)
# ---------------------------------------------------------------------------

@router.message(F.text == "📋 Меню")
async def open_menu(message: Message) -> None:
    """
    Кнопка постоянного меню. Сначала отправляем одно сообщение с премиум-эмодзи,
    затем, после небольшой паузы, — само инлайн-меню.
    """
    await message.answer(f'<tg-emoji emoji-id="{MENU_EMOJI_ID}">✨</tg-emoji>')
    await asyncio.sleep(MENU_EMOJI_DELAY)
    await message.answer("📋 Меню — выберите раздел:", reply_markup=kb.menu_inline())


@router.callback_query(F.data == "menu_back")
async def menu_back(callback: CallbackQuery) -> None:
    """Возврат в инлайн-меню из любого раздела (Профиль/Чаты/Реф.система)."""
    try:
        await callback.message.edit_text("📋 Меню — выберите раздел:", reply_markup=kb.menu_inline())
    except Exception:
        await callback.message.answer("📋 Меню — выберите раздел:", reply_markup=kb.menu_inline())
    await callback.answer()


@router.callback_query(F.data == "menu_referral")
async def menu_referral(callback: CallbackQuery, bot: Bot) -> None:
    """Раздел «🔗 Реферальная система» из инлайн-меню."""
    me = await bot.get_me()
    ref_link = f"https://t.me/{me.username}?start={callback.from_user.id}"
    text = (
        f"Ваша реферальная ссылка: \n\n{ref_link}\n\n"
        "Вы получаете 10% с первого профита реферала. Выплаты осуществляются администратором.\n"
        "Для получения выплаты отпишите: @manzi_nx или @jogas_wor"
    )

    # Путь к картинке — абсолютный, не зависит от рабочей директории процесса
    photo_path = IMAGES_DIR / "111.jpg"
    try:
        await callback.message.answer_photo(
            photo=FSInputFile(photo_path), caption=text, reply_markup=kb.menu_back_kb()
        )
    except Exception:
        # Картинка могла быть перемещена/удалена — не роняем хендлер,
        # отправляем хотя бы текст со ссылкой.
        await callback.message.answer(text, reply_markup=kb.menu_back_kb())
    await callback.answer()


@router.callback_query(F.data == "menu_profile")
async def menu_profile(callback: CallbackQuery, bot: Bot) -> None:
    """
    Раздел «👤 Профиль» из инлайн-меню: сумма профитов, количество рефералов,
    сколько дней в боте.
    Доступен только пользователям, состоящим в обязательном рабочем чате
    (chat_id настраивается администратором через /admin -> «🔒 Чат для вкладки
    «Профиль»»). Если чат не настроен админом (пустое значение) — проверка
    пропускается и профиль доступен всем.
    """
    user_id = callback.from_user.id
    required_chat_id = await db.get_setting("required_chat_id", "")
    required_chat_link = await db.get_setting("required_chat_link", "")

    if required_chat_id and not await is_chat_member(bot, required_chat_id, user_id):
        # Пользователь не состоит в обязательном чате — доступ к профилю закрыт.
        warning_text = (
            "🔒 Вкладка «Профиль» доступна только участникам нашего рабочего чата.\n\n"
            "Пожалуйста, вступите в чат по кнопке ниже и попробуйте снова 👇"
        )
        if required_chat_link:
            await callback.message.answer(warning_text, reply_markup=kb.join_chat_kb(required_chat_link))
        else:
            # Ссылка ещё не настроена админом — предупреждаем без кнопки.
            await callback.message.answer(
                warning_text + "\n\n(Ссылка на чат пока не настроена администратором.)",
                reply_markup=kb.menu_back_kb(),
            )
        await callback.answer()
        return

    # Пользователь прошёл проверку подписки (или проверка отключена) — показываем профиль.
    user = await db.get_user(user_id)
    if user is None:
        # На случай, если запись о пользователе почему-то отсутствует в БД —
        # создаём её "на лету", чтобы не ронять хендлер.
        await db.add_user(user_id, callback.from_user.username, callback.from_user.first_name, None)
        user = await db.get_user(user_id)

    referrals_count = await db.get_referrals_count(user_id)
    photo_path = IMAGES_DIR / "profile.png"
    try:
        await callback.message.answer_photo(
            photo=FSInputFile(photo_path),
            caption=format_profile(user, referrals_count),
            parse_mode="HTML",
            reply_markup=kb.profile_kb(),
        )
    except Exception:
        await callback.message.answer(
            format_profile(user, referrals_count), parse_mode="HTML", reply_markup=kb.profile_kb()
        )
    await callback.answer()


@router.callback_query(F.data == "menu_chats")
async def menu_chats(callback: CallbackQuery) -> None:
    """Раздел «💬 Чаты» из инлайн-меню: список ссылок, добавленных админом."""
    chats = await db.get_all_chats()
    if not chats:
        await callback.message.answer(
            "Пока нет добавленных чатов. Загляните позже 🙏", reply_markup=kb.menu_back_kb()
        )
        await callback.answer()
        return

    await callback.message.answer("💬 Чаты:", reply_markup=kb.chats_list_kb(chats))
    await callback.answer()


# ---------------------------------------------------------------------------
# Наставники
# ---------------------------------------------------------------------------

@router.callback_query(F.data == "mentors_list")
async def mentors_list(callback: CallbackQuery) -> None:
    """Показ списка наставников по кнопке «🎓 Наставники» из вкладки «Профиль»."""
    mentors = await db.get_all_mentors()
    if not mentors:
        await callback.message.answer("Пока нет доступных наставников. Загляните позже 🙏")
        await callback.answer()
        return

    await callback.message.answer("🎓 Наставники", reply_markup=kb.mentors_list_kb(mentors))
    await callback.answer()


@router.callback_query(F.data == "mentors_back_to_profile")
async def mentors_back_to_profile(callback: CallbackQuery) -> None:
    """Кнопка «⬅️ Назад» из списка наставников — возврат к вкладке «Профиль»."""
    user_id = callback.from_user.id
    user = await db.get_user(user_id)
    if user is None:
        await db.add_user(user_id, callback.from_user.username, callback.from_user.first_name, None)
        user = await db.get_user(user_id)

    referrals_count = await db.get_referrals_count(user_id)
    photo_path = IMAGES_DIR / "profile.png"
    try:
        await callback.message.answer_photo(
            photo=FSInputFile(photo_path),
            caption=format_profile(user, referrals_count),
            parse_mode="HTML",
            reply_markup=kb.profile_kb(),
        )
    except Exception:
        await callback.message.answer(
            format_profile(user, referrals_count), parse_mode="HTML", reply_markup=kb.profile_kb()
        )
    await callback.answer()


@router.callback_query(F.data == "mentors_home")
async def mentors_home(callback: CallbackQuery) -> None:
    """Кнопка «🏠 Домой» — выход из раздела наставников в инлайн-меню."""
    await callback.message.answer("📋 Меню — выберите раздел:", reply_markup=kb.menu_inline())
    await callback.answer()


@router.callback_query(F.data.startswith("mentor_view:"))
async def mentor_view(callback: CallbackQuery) -> None:
    """Показ карточки конкретного наставника."""
    mentor_id = int(callback.data.split(":", 1)[1])
    mentor = await db.get_mentor(mentor_id)
    if not mentor:
        await callback.answer("Этот наставник больше недоступен.", show_alert=True)
        return

    await callback.message.answer(format_mentor_card(mentor), reply_markup=kb.mentor_card_kb(mentor_id))
    await callback.answer()


@router.callback_query(F.data.startswith("mentor_apply:"))
async def mentor_apply(callback: CallbackQuery, bot: Bot) -> None:
    """Пользователь нажал «✅ Подать заявку» — закрепляем его за наставником."""
    mentor_id = int(callback.data.split(":", 1)[1])
    mentor = await _attach_user_to_mentor(
        bot,
        callback.from_user.id,
        callback.from_user.username,
        callback.from_user.first_name,
        mentor_id,
    )
    if not mentor:
        await callback.answer("Этот наставник больше недоступен.", show_alert=True)
        return

    await callback.message.answer(
        f"✅ Вы закрепились за наставником <b>{html_escape(mentor['name'])}</b>!\n"
        "Он свяжется с вами в ближайшее время."
    )
    await callback.answer("Готово ✅")


# ---------------------------------------------------------------------------
# Инлайн-режим: @<bot_username> ref / @<bot_username> <имя наставника>
# ---------------------------------------------------------------------------
# ВАЖНО: инлайн-режим нужно один раз включить у @BotFather командой /setinline
# для этого бота — без этого Telegram не будет присылать боту InlineQuery,
# даже если код обработчика полностью готов.

_REF_QUERY_ALIASES = {"ref", "реф", "referral", "рефка", "ссылка"}
_MAX_INLINE_RESULTS = 20


def _build_ref_result(bot_username: str, user_id: int) -> InlineQueryResultArticle:
    """Инлайн-результат: реферальная ссылка нажавшего пользователя."""
    ref_link = f"https://t.me/{bot_username}?start={user_id}"
    return InlineQueryResultArticle(
        id="ref",
        title="🔗 Моя реферальная ссылка",
        description=ref_link,
        input_message_content=InputTextMessageContent(
            message_text=(
                f"🔗 Реферальная ссылка:\n{ref_link}\n\n"
                "Переходи и начинай зарабатывать вместе с нами!"
            )
        ),
    )


def _build_mentor_result(bot_username: str, mentor: dict) -> InlineQueryResultArticle:
    """Инлайн-результат: карточка наставника со ссылкой на прикрепление к нему."""
    mentor_id = mentor["mentor_id"]
    deep_link = f"https://t.me/{bot_username}?start={MENTOR_DEEPLINK_PREFIX}{mentor_id}"

    # В description и в кнопке (title/description) HTML не поддерживается Telegram —
    # там используем «плоскую» подпись специализации (обычный эмодзи, без tg-emoji тега).
    spec_labels = specialization_keys_to_plain_labels(mentor.get("specialization"))
    spec_display = " • ".join(spec_labels) if spec_labels else "не указана"

    return InlineQueryResultArticle(
        id=f"mentor_{mentor_id}",
        title=f"🎓 {mentor['name']}",
        description=f"Специализация: {spec_display}",
        input_message_content=InputTextMessageContent(
            message_text=(
                f"🎓 Наставник: <b>{html_escape(mentor['name'])}</b>\n"
                f"Специализация: {spec_display}\n\n"
                f"✅ Закрепиться: {deep_link}"
            ),
            parse_mode="HTML",
        ),
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="✅ Закрепиться за наставником", url=deep_link)]
            ]
        ),
    )


@router.inline_query()
async def inline_query_handler(inline_query: InlineQuery, bot: Bot) -> None:
    """
    Обрабатывает инлайн-запросы вида «@<bot_username> ...» в любом чате:
    - пустой запрос или «ref» — своя реферальная ссылка (+ список наставников для удобства);
    - любой другой текст — поиск наставника по имени (подстрокой, без учёта регистра),
      результат — ссылка для прикрепления к нему.
    """
    query_text = (inline_query.query or "").strip()
    me = await bot.get_me()
    bot_username = me.username

    results: list[InlineQueryResultArticle] = []

    if not query_text:
        results.append(_build_ref_result(bot_username, inline_query.from_user.id))
        mentors = await db.get_all_mentors()
        results.extend(_build_mentor_result(bot_username, m) for m in mentors[:_MAX_INLINE_RESULTS])
    elif query_text.lower() in _REF_QUERY_ALIASES:
        results.append(_build_ref_result(bot_username, inline_query.from_user.id))
    else:
        mentors = await db.get_all_mentors()
        query_lower = query_text.lower()
        matched = [m for m in mentors if query_lower in m["name"].lower()]
        if matched:
            results.extend(_build_mentor_result(bot_username, m) for m in matched[:_MAX_INLINE_RESULTS])
        else:
            results.append(
                InlineQueryResultArticle(
                    id="not_found",
                    title="Наставник не найден",
                    description=f"Нет наставника с именем «{query_text}»",
                    input_message_content=InputTextMessageContent(
                        message_text=f"Наставник «{html_escape(query_text)}» не найден."
                    ),
                )
            )

    await inline_query.answer(results[:50], cache_time=10, is_personal=True)
