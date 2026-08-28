"""
Обработчики админ-панели: заявки, настройка группы, рассылка, рефералы.
"""

import asyncio
from typing import Optional

@@ -23,6 +24,7 @@
    PersonalMessage,
    ProfileChatSetup,
    ProfitAccrual,
    ProfitReset,
    RejectReason,
)
from utils import format_mentor_card
@@ -37,6 +39,7 @@ def _parse_percent(raw: str) -> Optional[float]:
    except ValueError:
        return None


router = Router(name="admin")


@@ -73,9 +76,7 @@ async def admin_back(callback: CallbackQuery, state: FSMContext) -> None:
async def show_pending(callback: CallbackQuery) -> None:
    if not _is_admin(callback.from_user.id):
        return await callback.answer()

    applications = await db.get_pending_applications()

    if not applications:
        await callback.message.answer(
            "Нерассмотренных заявок нет ✅", reply_markup=kb.admin_back_kb()
@@ -92,18 +93,15 @@ async def show_pending(callback: CallbackQuery) -> None:
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
@@ -113,7 +111,6 @@ async def accept_app(callback: CallbackQuery, bot: Bot) -> None:

    await db.update_application_status(app_id, "accepted")
    group_link = await db.get_setting("group_link", "Ссылка пока не настроена")

    try:
        await bot.send_message(
            application["user_id"],
@@ -128,18 +125,15 @@ async def accept_app(callback: CallbackQuery, bot: Bot) -> None:
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
@@ -149,7 +143,6 @@ async def reject_app_start(callback: CallbackQuery, state: FSMContext) -> None:

    await state.update_data(reject_app_id=app_id)
    await state.set_state(RejectReason.waiting_for_reason)

    await callback.message.answer(
        "Введите причину отклонения сообщением или нажмите «Пропустить»:",
        reply_markup=kb.skip_reason_kb(),
@@ -161,10 +154,8 @@ async def _finalize_rejection(bot: Bot, app_id: int, reason: Optional[str]) -> N
    application = await db.get_application(app_id)
    if not application or application["status"] != "pending":
        return

    await db.update_application_status(app_id, "rejected", reason)
    reason_text = reason if reason else "не указана"

    try:
        await bot.send_message(
            application["user_id"],
@@ -178,14 +169,11 @@ async def _finalize_rejection(bot: Bot, app_id: int, reason: Optional[str]) -> N
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

@@ -194,15 +182,12 @@ async def reject_app_reason(message: Message, state: FSMContext, bot: Bot) -> No
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
@@ -216,7 +201,6 @@ async def reject_app_skip(callback: CallbackQuery, state: FSMContext, bot: Bot)
async def group_setup_start(callback: CallbackQuery, state: FSMContext) -> None:
    if not _is_admin(callback.from_user.id):
        return await callback.answer()

    current_link = await db.get_setting("group_link", "не установлена")
    await state.set_state(GroupLinkSetup.waiting_for_link)
    await callback.message.answer(
@@ -229,7 +213,6 @@ async def group_setup_start(callback: CallbackQuery, state: FSMContext) -> None:
async def group_setup_process(message: Message, state: FSMContext) -> None:
    if not _is_admin(message.from_user.id):
        return

    await db.set_setting("group_link", message.text)
    await state.clear()
    await message.answer("✅ Ссылка на группу успешно обновлена!", reply_markup=kb.admin_back_kb())
@@ -243,7 +226,6 @@ async def group_setup_process(message: Message, state: FSMContext) -> None:
async def broadcast_start(callback: CallbackQuery, state: FSMContext) -> None:
    if not _is_admin(callback.from_user.id):
        return await callback.answer()

    await state.set_state(BroadcastForm.waiting_for_message)
    await callback.message.answer(
        "Отправьте сообщение (текст, фото, видео или документ) для рассылки всем пользователям бота:"
@@ -255,10 +237,8 @@ async def broadcast_start(callback: CallbackQuery, state: FSMContext) -> None:
async def broadcast_process(message: Message, state: FSMContext) -> None:
    if not _is_admin(message.from_user.id):
        return

    await state.clear()
    user_ids = await db.get_all_user_ids()

    status_message = await message.answer(f"⏳ Рассылка запущена... (0/{len(user_ids)})")

    sent, failed = 0, 0
@@ -284,9 +264,7 @@ async def broadcast_process(message: Message, state: FSMContext) -> None:
async def show_users(callback: CallbackQuery) -> None:
    if not _is_admin(callback.from_user.id):
        return await callback.answer()

    users = await db.get_all_users_with_referrers()

    if not users:
        await callback.message.answer("Пользователей пока нет.", reply_markup=kb.admin_back_kb())
        await callback.answer()
@@ -302,12 +280,10 @@ async def show_users(callback: CallbackQuery) -> None:
        lines.append(f"• {u['user_id']} (@{u['username'] or '—'}) — {ref_info}")

    full_text = "\n".join(lines)

    # Telegram ограничивает сообщение 4096 символами — режем на части при необходимости
    chunk_size = 3500
    for i in range(0, len(full_text), chunk_size):
        await callback.message.answer(full_text[i : i + chunk_size])

    await callback.message.answer("⬆️ Список выше.", reply_markup=kb.admin_back_kb())
    await callback.answer()

@@ -320,10 +296,8 @@ async def show_users(callback: CallbackQuery) -> None:
async def profile_chat_setup_start(callback: CallbackQuery, state: FSMContext) -> None:
    if not _is_admin(callback.from_user.id):
        return await callback.answer()

    current_chat_id = await db.get_setting("required_chat_id", "") or "не установлен (проверка выключена)"
    current_chat_link = await db.get_setting("required_chat_link", "") or "не установлена"

    await state.set_state(ProfileChatSetup.waiting_for_chat_id)
    await callback.message.answer(
        f"Текущий ID обязательного чата: {current_chat_id}\n"
@@ -340,10 +314,8 @@ async def profile_chat_setup_start(callback: CallbackQuery, state: FSMContext) -
async def profile_chat_setup_id(message: Message, state: FSMContext) -> None:
    if not _is_admin(message.from_user.id):
        return

    raw = (message.text or "").strip()
    chat_id_value = "" if raw == "-" else raw

    await db.set_setting("required_chat_id", chat_id_value)
    await state.set_state(ProfileChatSetup.waiting_for_chat_link)
    await message.answer(
@@ -356,7 +328,6 @@ async def profile_chat_setup_id(message: Message, state: FSMContext) -> None:
async def profile_chat_setup_link(message: Message, state: FSMContext) -> None:
    if not _is_admin(message.from_user.id):
        return

    await db.set_setting("required_chat_link", (message.text or "").strip())
    await state.clear()
    await message.answer(
@@ -373,7 +344,6 @@ async def profile_chat_setup_link(message: Message, state: FSMContext) -> None:
async def add_profit_start(callback: CallbackQuery, state: FSMContext) -> None:
    if not _is_admin(callback.from_user.id):
        return await callback.answer()

    await state.set_state(ProfitAccrual.waiting_for_user_id)
    await callback.message.answer("Введите Telegram ID пользователя, которому начисляем профит:")
    await callback.answer()
@@ -383,20 +353,17 @@ async def add_profit_start(callback: CallbackQuery, state: FSMContext) -> None:
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
@@ -406,21 +373,17 @@ async def add_profit_user_id(message: Message, state: FSMContext) -> None:
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
@@ -441,9 +404,7 @@ async def show_logs(callback: CallbackQuery) -> None:
    """
    if not _is_admin(callback.from_user.id):
        return await callback.answer()

    logs = await db.get_recent_logs(limit=50)

    if not logs:
        await callback.message.answer("Логов пока нет.", reply_markup=kb.admin_back_kb())
        await callback.answer()
@@ -456,12 +417,9 @@ async def show_logs(callback: CallbackQuery) -> None:
        lines.append(f"[{entry['created_at']}] {who} {action}: {entry['content']}")

    full_text = "\n".join(lines)

    # Telegram ограничивает сообщение 4096 символами — режем на части при необходимости
    chunk_size = 3500
    for i in range(0, len(full_text), chunk_size):
        await callback.message.answer(full_text[i : i + chunk_size])

    await callback.message.answer("⬆️ Логи выше.", reply_markup=kb.admin_back_kb())
    await callback.answer()

@@ -474,7 +432,6 @@ async def show_logs(callback: CallbackQuery) -> None:
async def admin_mentors_menu(callback: CallbackQuery, state: FSMContext) -> None:
    if not _is_admin(callback.from_user.id):
        return await callback.answer()

    await state.clear()
    mentors = await db.get_all_mentors()
    text = "🎓 Наставники:" if mentors else "🎓 Наставников пока нет. Добавьте первого!"
@@ -486,7 +443,6 @@ async def admin_mentors_menu(callback: CallbackQuery, state: FSMContext) -> None
async def admin_mentor_add_start(callback: CallbackQuery, state: FSMContext) -> None:
    if not _is_admin(callback.from_user.id):
        return await callback.answer()

    await state.set_state(MentorForm.waiting_for_name)
    await callback.message.answer("Введите имя нового наставника (например: MORF):")
    await callback.answer()
@@ -496,12 +452,10 @@ async def admin_mentor_add_start(callback: CallbackQuery, state: FSMContext) ->
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
@@ -514,7 +468,6 @@ async def admin_mentor_add_name(message: Message, state: FSMContext) -> None:
async def admin_mentor_add_description(message: Message, state: FSMContext) -> None:
    if not _is_admin(message.from_user.id):
        return

    description = message.text or ""
    await state.update_data(description=description, spec_selected=[])
    await state.set_state(MentorForm.waiting_for_specialization)
@@ -528,12 +481,10 @@ async def admin_mentor_add_description(message: Message, state: FSMContext) -> N
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
@@ -543,12 +494,10 @@ async def admin_mentor_add_percent(message: Message, state: FSMContext) -> None:
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
@@ -559,7 +508,6 @@ async def admin_mentor_add_profit_count(message: Message, state: FSMContext) ->

    mentor_id = await db.create_mentor(name, description, specialization, percent, profit_count)
    mentor = await db.get_mentor(mentor_id)

    await message.answer(
        "✅ Наставник добавлен!\n\n" + format_mentor_card(mentor),
        reply_markup=kb.admin_back_kb(),
@@ -574,7 +522,6 @@ async def admin_mentor_add_profit_count(message: Message, state: FSMContext) ->
async def mentor_spec_toggle(callback: CallbackQuery, state: FSMContext) -> None:
    if not _is_admin(callback.from_user.id):
        return await callback.answer()

    current_state = await state.get_state()
    if current_state not in (
        MentorForm.waiting_for_specialization,
@@ -607,7 +554,6 @@ async def mentor_spec_toggle(callback: CallbackQuery, state: FSMContext) -> None
async def mentor_spec_done(callback: CallbackQuery, state: FSMContext) -> None:
    if not _is_admin(callback.from_user.id):
        return await callback.answer()

    current_state = await state.get_state()
    data = await state.get_data()
    specialization = ",".join(data.get("spec_selected", []))
@@ -628,7 +574,6 @@ async def mentor_spec_done(callback: CallbackQuery, state: FSMContext) -> None:
                "✅ Специализация обновлена!",
                reply_markup=kb.admin_mentor_edit_menu_kb(mentor_id),
            )

    await callback.answer()


@@ -640,14 +585,12 @@ async def mentor_spec_done(callback: CallbackQuery, state: FSMContext) -> None:
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
@@ -658,7 +601,6 @@ async def admin_mentor_edit_menu(callback: CallbackQuery, state: FSMContext) ->
async def admin_mentor_edit_text_start(callback: CallbackQuery, state: FSMContext) -> None:
    if not _is_admin(callback.from_user.id):
        return await callback.answer()

    mentor_id = int(callback.data.split(":", 1)[1])
    await state.update_data(mentor_id=mentor_id)
    await state.set_state(MentorEditText.waiting_for_text)
@@ -670,14 +612,11 @@ async def admin_mentor_edit_text_start(callback: CallbackQuery, state: FSMContex
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

@@ -686,13 +625,11 @@ async def admin_mentor_edit_text_process(message: Message, state: FSMContext) ->
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
@@ -707,7 +644,6 @@ async def admin_mentor_edit_spec_start(callback: CallbackQuery, state: FSMContex
async def admin_mentor_edit_conditions_start(callback: CallbackQuery, state: FSMContext) -> None:
    if not _is_admin(callback.from_user.id):
        return await callback.answer()

    mentor_id = int(callback.data.split(":", 1)[1])
    await state.update_data(mentor_id=mentor_id)
    await state.set_state(MentorEditConditions.waiting_for_percent)
@@ -719,12 +655,10 @@ async def admin_mentor_edit_conditions_start(callback: CallbackQuery, state: FSM
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
@@ -734,21 +668,17 @@ async def admin_mentor_edit_conditions_percent(message: Message, state: FSMConte
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

@@ -761,7 +691,6 @@ async def admin_mentor_edit_conditions_count(message: Message, state: FSMContext
async def admin_mentor_delete_start(callback: CallbackQuery) -> None:
    if not _is_admin(callback.from_user.id):
        return await callback.answer()

    mentor_id = int(callback.data.split(":", 1)[1])
    await callback.message.answer(
        "Удалить этого наставника? Это действие необратимо, все закреплённые за ним "
@@ -775,10 +704,8 @@ async def admin_mentor_delete_start(callback: CallbackQuery) -> None:
async def admin_mentor_delete_confirm(callback: CallbackQuery) -> None:
    if not _is_admin(callback.from_user.id):
        return await callback.answer()

    mentor_id = int(callback.data.split(":", 1)[1])
    await db.delete_mentor(mentor_id)

    mentors = await db.get_all_mentors()
    await callback.message.answer("🗑 Наставник удалён.", reply_markup=kb.admin_mentors_menu_kb(mentors))
    await callback.answer()
@@ -792,7 +719,6 @@ async def admin_mentor_delete_confirm(callback: CallbackQuery) -> None:
async def admin_ban_user_start(callback: CallbackQuery, state: FSMContext) -> None:
    if not _is_admin(callback.from_user.id):
        return await callback.answer()

    await state.set_state(BanUser.waiting_for_user_id)
    await callback.message.answer("Введите Telegram ID пользователя для бана/разбана:")
    await callback.answer()
@@ -802,18 +728,14 @@ async def admin_ban_user_start(callback: CallbackQuery, state: FSMContext) -> No
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
@@ -824,39 +746,31 @@ async def admin_ban_user_id(message: Message, state: FSMContext) -> None:
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
        # Пользователь мог не запускать бота / уже заблокировать его — пропускаем
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
        # Пользователь мог не запускать бота / уже заблокировать его — пропускаем
        pass


@@ -868,7 +782,6 @@ async def admin_unban_confirm(callback: CallbackQuery, bot: Bot) -> None:
async def admin_message_user_start(callback: CallbackQuery, state: FSMContext) -> None:
    if not _is_admin(callback.from_user.id):
        return await callback.answer()

    await state.set_state(PersonalMessage.waiting_for_user_id)
    await callback.message.answer("Введите Telegram ID пользователя, которому нужно отправить сообщение:")
    await callback.answer()
@@ -878,20 +791,17 @@ async def admin_message_user_start(callback: CallbackQuery, state: FSMContext) -
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
@@ -904,14 +814,11 @@ async def admin_message_user_id(message: Message, state: FSMContext) -> None:
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
@@ -923,35 +830,40 @@ async def admin_message_user_send(message: Message, state: FSMContext) -> None:
            "(возможно, он не запускал бота или заблокировал его).",
            reply_markup=kb.admin_back_kb(),
        )
        


# ---------------------------------------------------------------------------
# Сброс профита пользователя по ID
# ---------------------------------------------------------------------------

@router.callback_query(F.data == "admin_reset_profit")
async def admin_reset_profit_start(callback: CallbackQuery, state: FSMContext):
    # Если не админ — сразу гасим анимацию кнопки и показываем предупреждение
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("У вас нет прав!", show_alert=True)
        return
async def admin_reset_profit_start(callback: CallbackQuery, state: FSMContext) -> None:
    if not _is_admin(callback.from_user.id):
        return await callback.answer("У вас нет прав!", show_alert=True)

    # Отвечаем Telegram в первую очередь, чтобы кнопка мгновенно отжала анимацию
    await callback.answer()
    
    await callback.message.edit_text(
        "Введите ID пользователя, которому нужно обнулить профит:",
        reply_markup=admin_back_kb(),
        reply_markup=kb.admin_back_kb(),
    )
    await state.set_state(ProfitReset.waiting_for_user_id)


@router.message(ProfitReset.waiting_for_user_id)
async def admin_reset_profit_apply(message: Message, state: FSMContext):
    if not message.text or not message.text.strip().lstrip("-").isdigit():
async def admin_reset_profit_apply(message: Message, state: FSMContext) -> None:
    if not _is_admin(message.from_user.id):
        return
    raw = (message.text or "").strip()
    if not raw.lstrip("-").isdigit():
        await message.answer("ID должен быть числом. Попробуйте ещё раз:")
        return

    user_id = int(message.text.strip())
    await db.reset_profit(user_id)
    target_user_id = int(raw)
    await db.reset_profit(target_user_id)
    await state.clear()

    await message.answer(
        f"Профит пользователя <code>{user_id}</code> обнулён.",
        f"✅ Профит пользователя <code>{target_user_id}</code> обнулён.",
        parse_mode="HTML",
        reply_markup=admin_menu(),
        reply_markup=kb.admin_menu(),
    )
