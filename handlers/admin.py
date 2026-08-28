"""
Обработчики админ-панели: заявки, настройка группы, рассылка, рефералы.
"""

import asyncio
from typing import Optional

from aiogram import Bot, F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

import database as db
import keyboards as kb
from config import ADMIN_IDS, MENTOR_SPECIALIZATIONS
from states import (
    BanUser,
    BroadcastForm,
    GroupLinkSetup,
    MentorEditConditions,
    MentorEditSpecialization,
    MentorEditText,
    MentorForm,
    PersonalMessage,
    ProfileChatSetup,
    ProfitAccrual,
    ProfitReset,
    RejectReason,
)
from utils import format_mentor_card

_MENTOR_SPEC_KEYS = {key for key, _, _ in MENTOR_SPECIALIZATIONS}


def _parse_percent(raw: str) -> Optional[float]:
    cleaned = raw.strip().replace(",", ".").replace("%", "")
    try:
        return float(cleaned)
    except ValueError:
        return None


router = Router(name="admin")


def _is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS


# ---------------------------------------------------------------------------
# Вход в панель
# ---------------------------------------------------------------------------

@router.message(Command("admin"))
async def cmd_admin(message: Message, state: FSMContext) -> None:
    if not _is_admin(message.from_user.id):
        return  # тихо игнорируем для не-админов
    await state.clear()
    await message.answer("🛠 Админ-панель", reply_markup=kb.admin_menu())


@router.callback_query(F.data == "admin_back")
async def admin_back(callback: CallbackQuery, state: FSMContext) -> None:
    if not _is_admin(callback.from_user.id):
        return await callback.answer()
    await state.clear()
    await callback.message.answer("🛠 Админ-панель", reply_markup=kb.admin_menu())
    await callback.answer()


# ---------------------------------------------------------------------------
# Нерассмотренные заявки
# ---------------------------------------------------------------------------

@router.callback_query(F.data == "admin_pending")
async def show_pending(callback: CallbackQuery) -> None:
    if not _is_admin(callback.from_user.id):
        return await callback.answer()
    applications = await db.get_pending_applications()
    if not applications:
        await callback.message.answer(
            "Нерассмотренных заявок нет ✅", reply_markup=kb.admin_back_kb()
        )
    else:
        for app in applications:
            text = (
                f"📋 Заявка #{app['app_id']}\n\n"
                f"ID пользователя: {app['user_id']}\n"
                f"Username: @{app['username'] or 'отсутствует'}\n\n"
                f"Анкета:\n{app['text']}"
            )
            await callback.message.answer(
                text, reply_markup=kb.application_decision_kb(app["app_id"])
            )
        await callback.message.answer("⬆️ Все нерассмотренные заявки выше.", reply_markup=kb.admin_back_kb())
    await callback.answer()


@router.callback_query(F.data.startswith("accept_app:"))
async def accept_app(callback: CallbackQuery, bot: Bot) -> None:
    if not _is_admin(callback.from_user.id):
        return await callback.answer()
    app_id = int(callback.data.split(":", 1)[1])
    application = await db.get_application(app_id)
    if not application:
        await callback.answer("Заявка не найдена.", show_alert=True)
        return
    if application["status"] != "pending":
        await callback.answer("Эта заявка уже обработана.", show_alert=True)
        return

    await db.update_application_status(app_id, "accepted")
    group_link = await db.get_setting("group_link", "Ссылка пока не настроена")
    try:
        await bot.send_message(
            application["user_id"],
            "🎉 Ваша заявка принята!\n\n"
            f"Ссылка на рабочую группу: {group_link}\n\n"
            "Удачных профитов! 💸",
        )
    except Exception:
        pass

    try:
        await callback.message.edit_text(callback.message.text + "\n\n✅ ПРИНЯТА")
    except Exception:
        pass
    await callback.answer("Заявка принята ✅")


@router.callback_query(F.data.startswith("reject_app:"))
async def reject_app_start(callback: CallbackQuery, state: FSMContext) -> None:
    if not _is_admin(callback.from_user.id):
        return await callback.answer()
    app_id = int(callback.data.split(":", 1)[1])
    application = await db.get_application(app_id)
    if not application:
        await callback.answer("Заявка не найдена.", show_alert=True)
        return
    if application["status"] != "pending":
        await callback.answer("Эта заявка уже обработана.", show_alert=True)
        return

    await state.update_data(reject_app_id=app_id)
    await state.set_state(RejectReason.waiting_for_reason)
    await callback.message.answer(
        "Введите причину отклонения сообщением или нажмите «Пропустить»:",
        reply_markup=kb.skip_reason_kb(),
    )
    await callback.answer()


async def _finalize_rejection(bot: Bot, app_id: int, reason: Optional[str]) -> None:
    application = await db.get_application(app_id)
    if not application or application["status"] != "pending":
        return
    await db.update_application_status(app_id, "rejected", reason)
    reason_text = reason if reason else "не указана"
    try:
        await bot.send_message(
            application["user_id"],
            f"Ваша заявка отклонена. Попробуйте снова. Причина: {reason_text}",
        )
    except Exception:
        pass


@router.message(RejectReason.waiting_for_reason)
async def reject_app_reason(message: Message, state: FSMContext, bot: Bot) -> None:
    if not _is_admin(message.from_user.id):
        return
    data = await state.get_data()
    app_id = data.get("reject_app_id")
    await state.clear()
    if app_id is None:
        return
    await _finalize_rejection(bot, app_id, message.text)
    await message.answer("❌ Заявка отклонена, причина отправлена пользователю.", reply_markup=kb.admin_back_kb())


@router.callback_query(F.data == "skip_reason")
async def reject_app_skip(callback: CallbackQuery, state: FSMContext, bot: Bot) -> None:
    if not _is_admin(callback.from_user.id):
        return await callback.answer()
    data = await state.get_data()
    app_id = data.get("reject_app_id")
    await state.clear()
    if app_id is None:
        await callback.answer()
        return
    await _finalize_rejection(bot, app_id, None)
    await callback.message.answer("❌ Заявка отклонена без указания причины.", reply_markup=kb.admin_back_kb())
    await callback.answer()


# ---------------------------------------------------------------------------
# Настройка ссылки на группу
# ---------------------------------------------------------------------------

@router.callback_query(F.data == "admin_group_setup")
async def group_setup_start(callback: CallbackQuery, state: FSMContext) -> None:
    if not _is_admin(callback.from_user.id):
        return await callback.answer()
    current_link = await db.get_setting("group_link", "не установлена")
    await state.set_state(GroupLinkSetup.waiting_for_link)
    await callback.message.answer(
        f"Текущая ссылка на группу:\n{current_link}\n\nОтправьте новую ссылку:"
    )
    await callback.answer()


@router.message(GroupLinkSetup.waiting_for_link)
async def group_setup_process(message: Message, state: FSMContext) -> None:
    if not _is_admin(message.from_user.id):
        return
    await db.set_setting("group_link", message.text)
    await state.clear()
    await message.answer("✅ Ссылка на группу успешно обновлена!", reply_markup=kb.admin_back_kb())


# ---------------------------------------------------------------------------
# Рассылка
# ---------------------------------------------------------------------------

@router.callback_query(F.data == "admin_broadcast")
async def broadcast_start(callback: CallbackQuery, state: FSMContext) -> None:
    if not _is_admin(callback.from_user.id):
        return await callback.answer()
    await state.set_state(BroadcastForm.waiting_for_message)
    await callback.message.answer(
        "Отправьте сообщение (текст, фото, видео или документ) для рассылки всем пользователям бота:"
    )
    await callback.answer()


@router.message(BroadcastForm.waiting_for_message)
async def broadcast_process(message: Message, state: FSMContext) -> None:
    if not _is_admin(message.from_user.id):
        return
    await state.clear()
    user_ids = await db.get_all_user_ids()
    status_message = await message.answer(f"⏳ Рассылка запущена... (0/{len(user_ids)})")

    sent, failed = 0, 0
    for uid in user_ids:
        try:
            await message.copy_to(uid)
            sent += 1
        except Exception:
            failed += 1
        await asyncio.sleep(0.05)  # мягкая защита от лимитов Telegram

    await status_message.edit_text(
        f"✅ Рассылка завершена!\nДоставлено: {sent}\nНе доставлено: {failed}"
    )
    await message.answer("Готово.", reply_markup=kb.admin_back_kb())


# ---------------------------------------------------------------------------
# Пользователи / рефералы
# ---------------------------------------------------------------------------

@router.callback_query(F.data == "admin_users")
async def show_users(callback: CallbackQuery) -> None:
    if not _is_admin(callback.from_user.id):
        return await callback.answer()
    users = await db.get_all_users_with_referrers()
    if not users:
        await callback.message.answer("Пользователей пока нет.", reply_markup=kb.admin_back_kb())
        await callback.answer()
        return

    lines = ["👥 Пользователи и их рефереры:\n"]
    for u in users:
        if u["referrer_id"]:
            ref_display = f"@{u['referrer_username']}" if u["referrer_username"] else str(u["referrer_id"])
            ref_info = f"приглашён {ref_display}"
        else:
            ref_info = "пришёл сам (без реферера)"
        lines.append(f"• {u['user_id']} (@{u['username'] or '—'}) — {ref_info}")

    full_text = "\n".join(lines)
    # Telegram ограничивает сообщение 4096 символами — режем на части при необходимости
    chunk_size = 3500
    for i in range(0, len(full_text), chunk_size):
        await callback.message.answer(full_text[i : i + chunk_size])
    await callback.message.answer("⬆️ Список выше.", reply_markup=kb.admin_back_kb())
    await callback.answer()


# ---------------------------------------------------------------------------
# Настройка обязательного чата для вкладки «Профиль»
# ---------------------------------------------------------------------------

@router.callback_query(F.data == "admin_profile_chat_setup")
async def profile_chat_setup_start(callback: CallbackQuery, state: FSMContext) -> None:
    if not _is_admin(callback.from_user.id):
        return await callback.answer()
    current_chat_id = await db.get_setting("required_chat_id", "") or "не установлен (проверка выключена)"
    current_chat_link = await db.get_setting("required_chat_link", "") or "не установлена"
    await state.set_state(ProfileChatSetup.waiting_for_chat_id)
    await callback.message.answer(
        f"Текущий ID обязательного чата: {current_chat_id}\n"
        f"Текущая ссылка-приглашение: {current_chat_link}\n\n"
        "Отправьте ID чата (например, -1001234567890) или @username публичного чата.\n\n"
        "⚠️ Бот должен быть добавлен в этот чат (рекомендуется — администратором), "
        "иначе проверка через Telegram API (getChatMember) работать не будет.\n\n"
        "Чтобы полностью отключить проверку подписки для вкладки «Профиль» — отправьте «-»."
    )
    await callback.answer()


@router.message(ProfileChatSetup.waiting_for_chat_id)
async def profile_chat_setup_id(message: Message, state: FSMContext) -> None:
    if not _is_admin(message.from_user.id):
        return
    raw = (message.text or "").strip()
    chat_id_value = "" if raw == "-" else raw
    await db.set_setting("required_chat_id", chat_id_value)
    await state.set_state(ProfileChatSetup.waiting_for_chat_link)
    await message.answer(
        "Теперь отправьте ссылку-приглашение в этот чат — она будет показана "
        "пользователю кнопкой, если он ещё не вступил:"
    )


@router.message(ProfileChatSetup.waiting_for_chat_link)
async def profile_chat_setup_link(message: Message, state: FSMContext) -> None:
    if not _is_admin(message.from_user.id):
        return
    await db.set_setting("required_chat_link", (message.text or "").strip())
    await state.clear()
    await message.answer(
        "✅ Настройки обязательного чата для вкладки «Профиль» обновлены!",
        reply_markup=kb.admin_back_kb(),
    )


# ---------------------------------------------------------------------------
# Начисление профита пользователю
# ---------------------------------------------------------------------------

@router.callback_query(F.data == "admin_add_profit")
async def add_profit_start(callback: CallbackQuery, state: FSMContext) -> None:
    if not _is_admin(callback.from_user.id):
        return await callback.answer()
    await state.set_state(ProfitAccrual.waiting_for_user_id)
    await callback.message.answer("Введите Telegram ID пользователя, которому начисляем профит:")
    await callback.answer()


@router.message(ProfitAccrual.waiting_for_user_id)
async def add_profit_user_id(message: Message, state: FSMContext) -> None:
    if not _is_admin(message.from_user.id):
        return
    raw = (message.text or "").strip()
    if not raw.isdigit():
        await message.answer("ID пользователя должен быть числом. Попробуйте ещё раз:")
        return
    target_user_id = int(raw)
    if not await db.user_exists(target_user_id):
        await message.answer(
            "Пользователь с таким ID не найден в базе бота. Проверьте ID и попробуйте снова "
            "(или отправьте /admin, чтобы отменить)."
        )
        return
    await state.update_data(target_user_id=target_user_id)
    await state.set_state(ProfitAccrual.waiting_for_amount)
    await message.answer("Введите сумму профита в рублях (например: 1500 или 1500.50):")


@router.message(ProfitAccrual.waiting_for_amount)
async def add_profit_amount(message: Message, state: FSMContext) -> None:
    if not _is_admin(message.from_user.id):
        return
    raw = (message.text or "").strip().replace(",", ".")
    try:
        amount = float(raw)
    except ValueError:
        await message.answer("Нужно ввести число. Попробуйте ещё раз (например: 1500.50):")
        return
    data = await state.get_data()
    target_user_id = data.get("target_user_id")
    await state.clear()
    if target_user_id is None:
        return
    await db.add_profit(target_user_id, amount)
    await message.answer(
        f"✅ Пользователю {target_user_id} начислено {amount:,.2f} ₽.".replace(",", " "),
        reply_markup=kb.admin_back_kb(),
    )


# ---------------------------------------------------------------------------
# Сброс профита пользователя по ID
# ---------------------------------------------------------------------------

@router.callback_query(F.data == "admin_reset_profit")
async def admin_reset_profit_start(callback: CallbackQuery, state: FSMContext) -> None:
    # Если не админ — сразу гасим анимацию кнопки и показываем предупреждение
    if not _is_admin(callback.from_user.id):
        await callback.answer("У вас нет прав!", show_alert=True)
        return

    # Отвечаем Telegram в первую очередь, чтобы кнопка мгновенно отжала анимацию
    await callback.answer()
    await callback.message.edit_text(
        "Введите ID пользователя, которому нужно обнулить профит:",
        reply_markup=kb.admin_back_kb(),
    )
    await state.set_state(ProfitReset.waiting_for_user_id)


@router.message(ProfitReset.waiting_for_user_id)
async def admin_reset_profit_apply(message: Message, state: FSMContext) -> None:
    if not _is_admin(message.from_user.id):
        return
    raw = (message.text or "").strip()
    if not raw.lstrip("-").isdigit():
        await message.answer("ID должен быть числом. Попробуйте ещё раз:")
        return

    target_user_id = int(raw)
    await db.reset_profit(target_user_id)
    await state.clear()

    await message.answer(
        f"✅ Профит пользователя <code>{target_user_id}</code> обнулён.",
        parse_mode="HTML",
        reply_markup=kb.admin_menu(),
    )


# ---------------------------------------------------------------------------
# Логи бота
# ---------------------------------------------------------------------------

@router.callback_query(F.data == "admin_logs")
async def show_logs(callback: CallbackQuery) -> None:
    """
    Показывает последние действия пользователей: какие кнопки нажимали
    и какие текстовые сообщения/команды отправляли.
    Данные собираются автоматически через middlewares.py для всех хендлеров бота.
    """
    if not _is_admin(callback.from_user.id):
        return await callback.answer()
    logs = await db.get_recent_logs(limit=50)
    if not logs:
        await callback.message.answer("Логов пока нет.", reply_markup=kb.admin_back_kb())
        await callback.answer()
        return

    lines = ["📝 Последние действия пользователей (не более 50):\n"]
    for entry in logs:
        who = f"@{entry['username']}" if entry["username"] else str(entry["user_id"])
        action = "нажал кнопку" if entry["event_type"] == "callback" else "написал"
        lines.append(f"[{entry['created_at']}] {who} {action}: {entry['content']}")

    full_text = "\n".join(lines)
    chunk_size = 3500
    for i in range(0, len(full_text), chunk_size):
        await callback.message.answer(full_text[i : i + chunk_size])
    await callback.message.answer("⬆️ Логи выше.", reply_markup=kb.admin_back_kb())
    await callback.answer()


# ---------------------------------------------------------------------------
# Наставники: список / добавление
# ---------------------------------------------------------------------------

@router.callback_query(F.data == "admin_mentors")
async def admin_mentors_menu(callback: CallbackQuery, state: FSMContext) -> None:
    if not _is_admin(callback.from_user.id):
        return await callback.answer()
    await state.clear()
    mentors = await db.get_all_mentors()
    text = "🎓 Наставники:" if mentors else "🎓 Наставников пока нет. Добавьте первого!"
    await callback.message.answer(text, reply_markup=kb.admin_mentors_menu_kb(mentors))
    await callback.answer()


@router.callback_query(F.data == "admin_mentor_add")
async def admin_mentor_add_start(callback: CallbackQuery, state: FSMContext) -> None:
    if not _is_admin(callback.from_user.id):
        return await callback.answer()
    await state.set_state(MentorForm.waiting_for_name)
    await callback.message.answer("Введите имя нового наставника (например: MORF):")
    await callback.answer()


@router.message(MentorForm.waiting_for_name)
async def admin_mentor_add_name(message: Message, state: FSMContext) -> None:
    if not _is_admin(message.from_user.id):
        return
    name = (message.text or "").strip()
    if not name:
        await message.answer("Имя не может быть пустым. Введите имя ещё раз:")
        return
    await state.update_data(name=name)
    await state.set_state(MentorForm.waiting_for_description)
    await message.answer(
        "Теперь отправьте текст «О наставнике» одним сообщением "
        "(описание, опыт, контакт и т.д. — этот текст полностью попадёт в карточку наставника):"
    )


@router.message(MentorForm.waiting_for_description)
async def admin_mentor_add_description(message: Message, state: FSMContext) -> None:
    if not _is_admin(message.from_user.id):
        return
    description = message.text or ""
    await state.update_data(description=description, spec_selected=[])
    await state.set_state(MentorForm.waiting_for_specialization)
    await message.answer(
        "Выберите специализацию наставника (можно несколько), затем нажмите «Готово ➡️»:",
        reply_markup=kb.mentor_spec_toggle_kb(set()),
    )


@router.message(MentorForm.waiting_for_percent)
async def admin_mentor_add_percent(message: Message, state: FSMContext) -> None:
    if not _is_admin(message.from_user.id):
        return
    percent = _parse_percent(message.text or "")
    if percent is None:
        await message.answer("Нужно ввести число, например 20. Попробуйте ещё раз:")
        return
    await state.update_data(percent=percent)
    await state.set_state(MentorForm.waiting_for_profit_count)
    await message.answer("Теперь введите количество профитов (целое число, например: 5):")


@router.message(MentorForm.waiting_for_profit_count)
async def admin_mentor_add_profit_count(message: Message, state: FSMContext) -> None:
    if not _is_admin(message.from_user.id):
        return
    raw = (message.text or "").strip()
    if not raw.lstrip("-").isdigit():
        await message.answer("Нужно ввести целое число, например 5. Попробуйте ещё раз:")
        return
    profit_count = int(raw)
    data = await state.get_data()
    name = data.get("name", "")
    description = data.get("description", "")
    specialization = ",".join(data.get("spec_selected", []))
    percent = data.get("percent", 0)
    await state.clear()

    mentor_id = await db.create_mentor(name, description, specialization, percent, profit_count)
    mentor = await db.get_mentor(mentor_id)
    await message.answer(
        "✅ Наставник добавлен!\n\n" + format_mentor_card(mentor),
        reply_markup=kb.admin_back_kb(),
    )


# ---------------------------------------------------------------------------
# Наставники: выбор специализации (общий шаг для создания и редактирования)
# ---------------------------------------------------------------------------

@router.callback_query(F.data.startswith("mentor_spec_toggle:"))
async def mentor_spec_toggle(callback: CallbackQuery, state: FSMContext) -> None:
    if not _is_admin(callback.from_user.id):
        return await callback.answer()
    current_state = await state.get_state()
    if current_state not in (
        MentorForm.waiting_for_specialization,
        MentorEditSpecialization.waiting_for_selection,
    ):
        await callback.answer()
        return

    key = callback.data.split(":", 1)[1]
    if key not in _MENTOR_SPEC_KEYS:
        await callback.answer()
        return

    data = await state.get_data()
    selected = set(data.get("spec_selected", []))
    if key in selected:
        selected.discard(key)
    else:
        selected.add(key)
    await state.update_data(spec_selected=list(selected))

    try:
        await callback.message.edit_reply_markup(reply_markup=kb.mentor_spec_toggle_kb(selected))
    except Exception:
        pass
    await callback.answer()


@router.callback_query(F.data == "mentor_spec_done")
async def mentor_spec_done(callback: CallbackQuery, state: FSMContext) -> None:
    if not _is_admin(callback.from_user.id):
        return await callback.answer()
    current_state = await state.get_state()
    data = await state.get_data()
    specialization = ",".join(data.get("spec_selected", []))

    if current_state == MentorForm.waiting_for_specialization:
        # Сценарий создания наставника: дальше — процент от профита.
        await state.set_state(MentorForm.waiting_for_percent)
        await callback.message.answer(
            "Специализация выбрана. Теперь введите процент от профита (например: 20):"
        )
    elif current_state == MentorEditSpecialization.waiting_for_selection:
        # Сценарий редактирования: сразу сохраняем в БД.
        mentor_id = data.get("mentor_id")
        await state.clear()
        if mentor_id is not None:
            await db.update_mentor_specialization(mentor_id, specialization)
            await callback.message.answer(
                "✅ Специализация обновлена!",
                reply_markup=kb.admin_mentor_edit_menu_kb(mentor_id),
            )
    await callback.answer()


# ---------------------------------------------------------------------------
# Наставники: редактирование существующего
# ---------------------------------------------------------------------------

@router.callback_query(F.data.startswith("admin_mentor_edit:"))
async def admin_mentor_edit_menu(callback: CallbackQuery, state: FSMContext) -> None:
    if not _is_admin(callback.from_user.id):
        return await callback.answer()
    await state.clear()
    mentor_id = int(callback.data.split(":", 1)[1])
    mentor = await db.get_mentor(mentor_id)
    if not mentor:
        await callback.answer("Наставник не найден.", show_alert=True)
        return
    await callback.message.answer(
        format_mentor_card(mentor), reply_markup=kb.admin_mentor_edit_menu_kb(mentor_id)
    )
    await callback.answer()


@router.callback_query(F.data.startswith("admin_mentor_edit_text:"))
async def admin_mentor_edit_text_start(callback: CallbackQuery, state: FSMContext) -> None:
    if not _is_admin(callback.from_user.id):
        return await callback.answer()
    mentor_id = int(callback.data.split(":", 1)[1])
    await state.update_data(mentor_id=mentor_id)
    await state.set_state(MentorEditText.waiting_for_text)
    await callback.message.answer("Отправьте новый текст «О наставнике» одним сообщением:")
    await callback.answer()


@router.message(MentorEditText.waiting_for_text)
async def admin_mentor_edit_text_process(message: Message, state: FSMContext) -> None:
    if not _is_admin(message.from_user.id):
        return
    data = await state.get_data()
    mentor_id = data.get("mentor_id")
    await state.clear()
    if mentor_id is None:
        return
    await db.update_mentor_description(mentor_id, message.text or "")
    await message.answer("✅ Текст обновлён!", reply_markup=kb.admin_mentor_edit_menu_kb(mentor_id))


@router.callback_query(F.data.startswith("admin_mentor_edit_spec:"))
async def admin_mentor_edit_spec_start(callback: CallbackQuery, state: FSMContext) -> None:
    if not _is_admin(callback.from_user.id):
        return await callback.answer()
    mentor_id = int(callback.data.split(":", 1)[1])
    mentor = await db.get_mentor(mentor_id)
    if not mentor:
        await callback.answer("Наставник не найден.", show_alert=True)
        return
    current = {k.strip() for k in (mentor.get("specialization") or "").split(",") if k.strip()}
    await state.update_data(mentor_id=mentor_id, spec_selected=list(current))
    await state.set_state(MentorEditSpecialization.waiting_for_selection)
    await callback.message.answer(
        "Выберите специализацию (можно несколько), затем нажмите «Готово ➡️»:",
        reply_markup=kb.mentor_spec_toggle_kb(current),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("admin_mentor_edit_conditions:"))
async def admin_mentor_edit_conditions_start(callback: CallbackQuery, state: FSMContext) -> None:
    if not _is_admin(callback.from_user.id):
        return await callback.answer()
    mentor_id = int(callback.data.split(":", 1)[1])
    await state.update_data(mentor_id=mentor_id)
    await state.set_state(MentorEditConditions.waiting_for_percent)
    await callback.message.answer("Введите новый процент от профита (например: 20):")
    await callback.answer()


@router.message(MentorEditConditions.waiting_for_percent)
async def admin_mentor_edit_conditions_percent(message: Message, state: FSMContext) -> None:
    if not _is_admin(message.from_user.id):
        return
    percent = _parse_percent(message.text or "")
    if percent is None:
        await message.answer("Нужно ввести число, например 20. Попробуйте ещё раз:")
        return
    await state.update_data(percent=percent)
    await state.set_state(MentorEditConditions.waiting_for_profit_count)
    await message.answer("Теперь введите количество профитов (целое число, например: 5):")


@router.message(MentorEditConditions.waiting_for_profit_count)
async def admin_mentor_edit_conditions_count(message: Message, state: FSMContext) -> None:
    if not _is_admin(message.from_user.id):
        return
    raw = (message.text or "").strip()
    if not raw.lstrip("-").isdigit():
        await message.answer("Нужно ввести целое число, например 5. Попробуйте ещё раз:")
        return
    profit_count = int(raw)
    data = await state.get_data()
    mentor_id = data.get("mentor_id")
    percent = data.get("percent", 0)
    await state.clear()
    if mentor_id is None:
        return
    await db.update_mentor_conditions(mentor_id, percent, profit_count)
    await message.answer("✅ Условия обновлены!", reply_markup=kb.admin_mentor_edit_menu_kb(mentor_id))


# ---------------------------------------------------------------------------
# Наставники: удаление
# ---------------------------------------------------------------------------

@router.callback_query(F.data.startswith("admin_mentor_delete:"))
async def admin_mentor_delete_start(callback: CallbackQuery) -> None:
    if not _is_admin(callback.from_user.id):
        return await callback.answer()
    mentor_id = int(callback.data.split(":", 1)[1])
    await callback.message.answer(
        "Удалить этого наставника? Это действие необратимо, все закреплённые за ним "
        "пользователи будут откреплены.",
        reply_markup=kb.admin_mentor_delete_confirm_kb(mentor_id),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("admin_mentor_delete_confirm:"))
async def admin_mentor_delete_confirm(callback: CallbackQuery) -> None:
    if not _is_admin(callback.from_user.id):
        return await callback.answer()
    mentor_id = int(callback.data.split(":", 1)[1])
    await db.delete_mentor(mentor_id)
    mentors = await db.get_all_mentors()
    await callback.message.answer("🗑 Наставник удалён.", reply_markup=kb.admin_mentors_menu_kb(mentors))
    await callback.answer()


# ---------------------------------------------------------------------------
# Бан / разбан пользователя по ID
# ---------------------------------------------------------------------------

@router.callback_query(F.data == "admin_ban_user")
async def admin_ban_user_start(callback: CallbackQuery, state: FSMContext) -> None:
    if not _is_admin(callback.from_user.id):
        return await callback.answer()
    await state.set_state(BanUser.waiting_for_user_id)
    await callback.message.answer("Введите Telegram ID пользователя для бана/разбана:")
    await callback.answer()


@router.message(BanUser.waiting_for_user_id)
async def admin_ban_user_id(message: Message, state: FSMContext) -> None:
    if not _is_admin(message.from_user.id):
        return
    raw = (message.text or "").strip()
    if not raw.isdigit():
        await message.answer("ID пользователя должен быть числом. Попробуйте ещё раз:")
        return
    target_user_id = int(raw)
    await state.clear()
    is_banned = await db.is_user_banned(target_user_id)
    status_text = "🚫 сейчас забанен" if is_banned else "✅ сейчас не забанен"
    await message.answer(
        f"Пользователь {target_user_id} {status_text}.\nВыберите действие:",
        reply_markup=kb.admin_ban_action_kb(target_user_id, is_banned),
    )


@router.callback_query(F.data.startswith("admin_ban_confirm:"))
async def admin_ban_confirm(callback: CallbackQuery, bot: Bot) -> None:
    if not _is_admin(callback.from_user.id):
        return await callback.answer()
    target_user_id = int(callback.data.split(":", 1)[1])
    await db.set_user_banned(target_user_id, True)
    await callback.message.answer(
        f"🚫 Пользователь {target_user_id} забанен.", reply_markup=kb.admin_back_kb()
    )
    await callback.answer("Забанен 🚫")
    try:
        await bot.send_message(target_user_id, "🚫 Вы были заблокированы в этом боте.")
    except Exception:
        pass


@router.callback_query(F.data.startswith("admin_unban_confirm:"))
async def admin_unban_confirm(callback: CallbackQuery, bot: Bot) -> None:
    if not _is_admin(callback.from_user.id):
        return await callback.answer()
    target_user_id = int(callback.data.split(":", 1)[1])
    await db.set_user_banned(target_user_id, False)
    await callback.message.answer(
        f"✅ Пользователь {target_user_id} разбанен.", reply_markup=kb.admin_back_kb()
    )
    await callback.answer("Разбанен ✅")
    try:
        await bot.send_message(target_user_id, "✅ Вы снова можете пользоваться этим ботом.")
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Сообщение одному пользователю по ID
# ---------------------------------------------------------------------------

@router.callback_query(F.data == "admin_message_user")
async def admin_message_user_start(callback: CallbackQuery, state: FSMContext) -> None:
    if not _is_admin(callback.from_user.id):
        return await callback.answer()
    await state.set_state(PersonalMessage.waiting_for_user_id)
    await callback.message.answer("Введите Telegram ID пользователя, которому нужно отправить сообщение:")
    await callback.answer()


@router.message(PersonalMessage.waiting_for_user_id)
async def admin_message_user_id(message: Message, state: FSMContext) -> None:
    if not _is_admin(message.from_user.id):
        return
    raw = (message.text or "").strip()
    if not raw.isdigit():
        await message.answer("ID пользователя должен быть числом. Попробуйте ещё раз:")
        return
    target_user_id = int(raw)
    if not await db.user_exists(target_user_id):
        await message.answer(
            "Пользователь с таким ID не найден в базе бота. Проверьте ID и попробуйте снова "
            "(или отправьте /admin, чтобы отменить)."
        )
        return
    await state.update_data(target_user_id=target_user_id)
    await state.set_state(PersonalMessage.waiting_for_message)
    await message.answer(
        "Отправьте сообщение (текст, фото, видео или документ), которое нужно переслать "
        "этому пользователю:"
    )


@router.message(PersonalMessage.waiting_for_message)
async def admin_message_user_send(message: Message, state: FSMContext) -> None:
    if not _is_admin(message.from_user.id):
        return
    data = await state.get_data()
    target_user_id = data.get("target_user_id")
    await state.clear()
    if target_user_id is None:
        return
    try:
        await message.copy_to(target_user_id)
        await message.answer(
            f"✅ Сообщение отправлено пользователю {target_user_id}.", reply_markup=kb.admin_back_kb()
        )
    except Exception:
        await message.answer(
            f"❌ Не удалось отправить сообщение пользователю {target_user_id} "
            "(возможно, он не запускал бота или заблокировал его).",
            reply_markup=kb.admin_back_kb(),
        )
