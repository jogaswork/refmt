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
from config import ADMIN_IDS
from states import BroadcastForm, GroupLinkSetup, RejectReason

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
