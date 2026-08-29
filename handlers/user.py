"""
Обработчики пользовательского сценария:
/start -> подача заявки -> уведомление админов; реферальная система; меню.
"""

import asyncio
from html import escape as html_escape
from pathlib import Path
from typing import Optional

from aiogram import Bot, F, Router
from aiogram.filters import Command, CommandObject, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import (
    BufferedInputFile,
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
import profile_render
import ranks
from config import ADMIN_IDS
from states import ApplicationForm, NicknameChange
from utils import (
    application_eligibility,
    format_mentor_card,
    format_profile,
    is_chat_member,
    specialization_keys_to_plain_labels,
)

router = Router(name="user")

IMAGES_DIR = Path(__file__).resolve().parent.parent / "images"

NEW_REFERRAL_EMOJI_ID = "5458824569026532353"
# Эмодзи-заставка перед главным меню (см. show_main_menu).
MENU_INTRO_EMOJI_ID = "5893057118545646106"
MENU_INTRO_DELAY = 0.7  # секунд между эмодзи и самим меню

MENTOR_DEEPLINK_PREFIX = "mentor_"

NICKNAME_MIN_LEN = 2
NICKNAME_MAX_LEN = 20

ANKET_TEXT = (
    "🚀 Перед тем, как начать зарабатывать миллионы, нужно ответить на несколько вопросов!\n\n"
    "1. Опишите свой опыт работы в данной сфере? (Где раньше воркали, на каких площадках, сколько заработали)\n"
    "2. Сколько времени готовы уделять работе?\n"
    "3. Откуда узнали о нас? (Ссылка на друга или бота, или тикток)\n\n"
    "👁️ Ответ писать ОДНИМ сообщением в ОТВЕТ на это, заявки не по форме будут автоматически отклоняться!"
)


async def _attach_user_to_mentor(
    bot: Bot, user_id: int, username: str | None, first_name: str | None, mentor_id: int
) -> Optional[dict]:
    mentor = await db.get_mentor(mentor_id)
    if not mentor:
        return None

    if not await db.user_exists(user_id):
        await db.add_user(user_id, username, first_name, None)
    await db.set_user_mentor(user_id, mentor_id)

    who = html_escape(f"@{username}" if username else (first_name or str(user_id)))
    admin_text = (
        f"🎓 Пользователь {who} (ID: {user_id}) закрепился за наставником «{html_escape(mentor['name'])}»."
    )
    for admin_id in ADMIN_IDS:
        try:
            await bot.send_message(admin_id, admin_text)
        except Exception:
            continue

    return mentor


@router.message(CommandStart())
async def cmd_start(message: Message, command: CommandObject, state: FSMContext, bot: Bot) -> None:
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
            pass

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

    await message.answer(
        "Используй меню ниже, чтобы перейти в реферальную систему в любой момент 👇",
        reply_markup=kb.main_menu_reply(),
    )

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
    answer_text = message.text or message.caption
    if not answer_text:
        await message.answer("Пожалуйста, ответьте на анкету текстовым сообщением 🙏")
        return

    app_id = await db.create_application(
        user_id=message.from_user.id, username=message.from_user.username, text=answer_text
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
            continue


# ---------------------------------------------------------------------------
# Главное меню: «📋 Меню» -> эмодзи-заставка -> инлайн-меню
# ---------------------------------------------------------------------------

MENU_IMAGE_PATH = Path(__file__).resolve().parent.parent / "images" / "menu.png"
RANKS_IMAGE_PATH = Path(__file__).resolve().parent.parent / "images" / "rang.jpg"

# Эмодзи, которое ставится в начало сообщения с рангами (по требованию заказчика).
RANK_EMOJI_ID = "5278296377632250061"


MAIN_MENU_TITLE = (
"f'<tg-emoji emoji-id="5886223731088431288">📋</tg-emoji> Главное меню"
"Информация о проекте MTR TEAM"
"└ Дата запуска: 28.08.2026"
"Процент выплат:"
"├ Прямой перевод: 80%"
"├ Крипто деп: 80%"
"├ Пополнение: 80%"
"└ Тех. поддержка: 70%"
)

async def _send_main_menu(message: Message, user_id: int) -> None:
    """Отправляет меню картинкой images/menu.png с подписью и инлайн-кнопками."""
    is_admin = user_id in ADMIN_IDS
    try:
        await message.answer_photo(
            photo=FSInputFile(MENU_IMAGE_PATH),
            caption=MAIN_MENU_TITLE,
            reply_markup=kb.main_menu_inline(is_admin),
        )
    except Exception:
        # Картинка могла быть не положена в images/menu.png — не роняем меню,
        # отправляем хотя бы текстовый вариант.
        await message.answer(MAIN_MENU_TITLE, reply_markup=kb.main_menu_inline(is_admin))


@router.message(F.text == "📋 Меню")
@router.message(F.text == "Меню")
async def show_main_menu(message: Message) -> None:
    """
    Кнопка «📋 Меню»: сначала отправляется одно сообщение с эмодзи-заставкой,
    затем — через небольшую паузу — само меню картинкой (Профиль / Реферальная
    система / Ранги / Чаты, и «🛠 Админ-панель» — только для админов).
    """
    await message.answer(f'<tg-emoji emoji-id="{MENU_INTRO_EMOJI_ID}">🔥</tg-emoji>')
    await asyncio.sleep(MENU_INTRO_DELAY)
    await _send_main_menu(message, message.from_user.id)


@router.callback_query(F.data == "menu_back")
async def menu_back(callback: CallbackQuery) -> None:
    """Возврат в меню без повторной эмодзи-заставки (уже показывали её)."""
    await _send_main_menu(callback.message, callback.from_user.id)
    await callback.answer()


@router.callback_query(F.data == "menu_ranks")
async def menu_ranks(callback: CallbackQuery) -> None:
    """Пункт меню «🏆 Ранги» — картинка images/rang.jpg + список рангов, текущий помечен."""
    user = await db.get_user(callback.from_user.id)
    profit = (user.get("profit") if user else 0) or 0
    current_rank = ranks.get_rank(profit)

    caption = (
        f'<tg-emoji emoji-id="{RANK_EMOJI_ID}">🏆</tg-emoji> Ваш текущий ранг: <b>{current_rank}</b>\n\n'
        f"{ranks.format_ranks_list(profit)}"
    )

    try:
        await callback.message.answer_photo(
            photo=FSInputFile(RANKS_IMAGE_PATH), caption=caption, reply_markup=kb.back_to_menu_kb()
        )
    except Exception:
        await callback.message.answer(caption, reply_markup=kb.back_to_menu_kb())
    await callback.answer()


@router.callback_query(F.data == "menu_referral")
async def menu_referral(callback: CallbackQuery, bot: Bot) -> None:
    """Пункт меню «🔗 Реферальная система» — та же логика, что была раньше на кнопке."""
    me = await bot.get_me()
    ref_link = f"https://t.me/{me.username}?start={callback.from_user.id}"

    text = (
        f"Ваша реферальная ссылка: \n\n{ref_link}\n\n"
        "Вы получаете 10% с первого профита реферала. Выплаты осуществляются администратором.\n"
        "Для получения выплаты отпишите: @manzi_nx или @jogas_wor"
    )

    photo_path = IMAGES_DIR / "111.jpg"
    try:
        await callback.message.answer_photo(photo=FSInputFile(photo_path), caption=text)
    except Exception:
        await callback.message.answer(text)
    await callback.answer()


@router.callback_query(F.data == "menu_chats")
async def menu_chats(callback: CallbackQuery) -> None:
    """Пункт меню «💬 Чаты» — список ссылок, которые настроил админ."""
    chats = await db.get_all_chat_links()
    if not chats:
        await callback.message.answer(
            "Пока нет добавленных чатов. Загляните позже 🙏", reply_markup=kb.back_to_menu_kb()
        )
        await callback.answer()
        return

    await callback.message.answer("💬Наши чаты:", reply_markup=kb.chats_list_kb(chats))
    await callback.answer()


# ---------------------------------------------------------------------------
# Профиль
# ---------------------------------------------------------------------------

async def _send_profile_card(message: Message, user_id: int) -> None:
    """
    Отправляет графическую карточку профиля (assets/profile.png + данные) с
    текстом format_profile() + текущим рангом в подписи и кнопками (наставники /
    смена ника / меню).
    """
    user = await db.get_user(user_id)
    if user is None:
        await db.add_user(user_id, message.from_user.username, message.from_user.first_name, None)
        user = await db.get_user(user_id)

    referrals_count = await db.get_referrals_count(user_id)
    rank_line = (
        f'<tg-emoji emoji-id="{RANK_EMOJI_ID}">🏆</tg-emoji> '
        f"Ранг: <b>{ranks.get_rank(user.get('profit') or 0)}</b>"
    )
    caption = f"{format_profile(user, referrals_count)}\n\n{rank_line}"

    try:
        card_bytes = profile_render.generate_profile_card(user, referrals_count)
        photo = BufferedInputFile(card_bytes.read(), filename="profile.jpg")
        await message.answer_photo(photo=photo, caption=caption, reply_markup=kb.profile_kb())
    except Exception:
        # Если картинка почему-то не собралась (нет шаблона/шрифта на сервере) —
        # не роняем хендлер, показываем хотя бы прежний текстовый профиль.
        await message.answer(caption, reply_markup=kb.profile_kb())


@router.callback_query(F.data == "menu_profile")
async def menu_profile(callback: CallbackQuery, bot: Bot) -> None:
    """Пункт меню «👤 Профиль» — та же проверка обязательного чата, что была раньше."""
    user_id = callback.from_user.id
    required_chat_id = await db.get_setting("required_chat_id", "")
    required_chat_link = await db.get_setting("required_chat_link", "")

    if required_chat_id and not await is_chat_member(bot, required_chat_id, user_id):
        warning_text = (
            "🔒 Профиль доступен только участникам нашего рабочего чата.\n\n"
            "Пожалуйста, вступите в чат по кнопке ниже и попробуйте снова 👇"
        )
        if required_chat_link:
            await callback.message.answer(warning_text, reply_markup=kb.join_chat_kb(required_chat_link))
        else:
            await callback.message.answer(
                warning_text + "\n\n(Ссылка на чат пока не настроена администратором.)"
            )
        await callback.answer()
        return

    await _send_profile_card(callback.message, user_id)
    await callback.answer()


@router.message(Command("profile"))
async def cmd_profile(message: Message, bot: Bot) -> None:
    """Команда /profile — то же самое, что и пункт меню «👤 Профиль»."""
    user_id = message.from_user.id
    required_chat_id = await db.get_setting("required_chat_id", "")
    required_chat_link = await db.get_setting("required_chat_link", "")

    if required_chat_id and not await is_chat_member(bot, required_chat_id, user_id):
        warning_text = (
            "🔒 Профиль доступен только участникам нашего рабочего чата.\n\n"
            "Пожалуйста, вступите в чат по кнопке ниже и попробуйте снова 👇"
        )
        if required_chat_link:
            await message.answer(warning_text, reply_markup=kb.join_chat_kb(required_chat_link))
        else:
            await message.answer(warning_text + "\n\n(Ссылка на чат пока не настроена администратором.)")
        return

    await _send_profile_card(message, user_id)


# ---------------------------------------------------------------------------
# Смена ника в карточке профиля
# ---------------------------------------------------------------------------

@router.callback_query(F.data == "profile_change_nick")
async def profile_change_nick(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(NicknameChange.waiting_for_nickname)
    await callback.message.answer(
        f"Введите новый ник (от {NICKNAME_MIN_LEN} до {NICKNAME_MAX_LEN} символов).\n"
        "Отправьте /cancel, чтобы отменить."
    )
    await callback.answer()


@router.message(Command("cancel"), NicknameChange.waiting_for_nickname)
async def cancel_change_nick(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer("Отменено.")


@router.message(NicknameChange.waiting_for_nickname)
async def process_new_nickname(message: Message, state: FSMContext) -> None:
    new_nick = (message.text or "").strip()

    if not (NICKNAME_MIN_LEN <= len(new_nick) <= NICKNAME_MAX_LEN):
        await message.answer(
            f"Ник должен быть от {NICKNAME_MIN_LEN} до {NICKNAME_MAX_LEN} символов. Попробуйте ещё раз."
        )
        return

    await db.set_user_nickname(message.from_user.id, new_nick)
    await state.clear()

    await message.answer(f"Ник обновлён: <b>{html_escape(new_nick)}</b>")
    await _send_profile_card(message, message.from_user.id)


# ---------------------------------------------------------------------------
# Наставники
# ---------------------------------------------------------------------------

@router.callback_query(F.data == "mentors_list")
async def mentors_list(callback: CallbackQuery) -> None:
    mentors = await db.get_all_mentors()
    if not mentors:
        await callback.message.answer("Пока нет доступных наставников. Загляните позже 🙏")
        await callback.answer()
        return

    await callback.message.answer("🎓 Наставники", reply_markup=kb.mentors_list_kb(mentors))
    await callback.answer()


@router.callback_query(F.data == "mentors_back_to_profile")
async def mentors_back_to_profile(callback: CallbackQuery) -> None:
    await _send_profile_card(callback.message, callback.from_user.id)
    await callback.answer()


@router.callback_query(F.data == "mentors_home")
async def mentors_home(callback: CallbackQuery) -> None:
    await _send_main_menu(callback.message, callback.from_user.id)
    await callback.answer()


@router.callback_query(F.data.startswith("mentor_view:"))
async def mentor_view(callback: CallbackQuery) -> None:
    mentor_id = int(callback.data.split(":", 1)[1])
    mentor = await db.get_mentor(mentor_id)
    if not mentor:
        await callback.answer("Этот наставник больше недоступен.", show_alert=True)
        return

    await callback.message.answer(format_mentor_card(mentor), reply_markup=kb.mentor_card_kb(mentor_id))
    await callback.answer()


@router.callback_query(F.data.startswith("mentor_apply:"))
async def mentor_apply(callback: CallbackQuery, bot: Bot) -> None:
    mentor_id = int(callback.data.split(":", 1)[1])
    mentor = await _attach_user_to_mentor(
        bot, callback.from_user.id, callback.from_user.username, callback.from_user.first_name, mentor_id
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

_REF_QUERY_ALIASES = {"ref", "реф", "referral", "рефка", "ссылка"}
_MAX_INLINE_RESULTS = 20


def _build_ref_result(bot_username: str, user_id: int) -> InlineQueryResultArticle:
    ref_link = f"https://t.me/{bot_username}?start={user_id}"
    return InlineQueryResultArticle(
        id="ref",
        title="🔗 Моя реферальная ссылка",
        description=ref_link,
        input_message_content=InputTextMessageContent(
            message_text=(
                f"🔗 Реферальная ссылка:\n{ref_link}\n\nПереходи и начинай зарабатывать вместе с нами!"
            )
        ),
    )


def _build_mentor_result(bot_username: str, mentor: dict) -> InlineQueryResultArticle:
    mentor_id = mentor["mentor_id"]
    deep_link = f"https://t.me/{bot_username}?start={MENTOR_DEEPLINK_PREFIX}{mentor_id}"

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
            inline_keyboard=[[InlineKeyboardButton(text="✅ Закрепиться за наставником", url=deep_link)]]
        ),
    )


@router.inline_query()
async def inline_query_handler(inline_query: InlineQuery, bot: Bot) -> None:
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
