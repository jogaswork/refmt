# -*- coding: utf-8 -*-
"""
Рендер графической карточки профиля поверх assets/profile.png.

Кладите сюда:
    assets/profile.png            — шаблон карточки (файл, который вы прислали)
    fonts/Montserrat-Bold.ttf     — шрифт (скачать на fonts.google.com)
"""

import io
import datetime
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont

BASE_DIR = Path(__file__).resolve().parent

TEMPLATE_PATH = BASE_DIR / "assets" / "profile.png"
FONT_PATH = BASE_DIR / "fonts" / "Montserrat-Bold.ttf"

FONT_SIZE = 36
TEXT_COLOR = (255, 255, 255)
MIN_FONT_SIZE = 18
BOX_PADDING_X = 24

# Координаты вычислены по пикселям фактического шаблона (1672x941 px).
# box: (x0, y0, x1, y1) — рамка инпута, текст центрируется внутри неё.
FIELD_BOXES = {
    "nickname": (510, 345, 1140, 435),   # ✦ НИКНЕЙМ ✦
    "days":     (1205, 345, 1580, 435),  # ДНЕЙ В ТИМЕ
    "sum":      (455, 565, 790, 645),    # СУММА ПРОФИТОВ
    "max":      (840, 565, 1150, 645),   # МАКС. ПРОФИТ
    "refs":     (1205, 565, 1580, 645),  # КОЛИЧЕСТВО РЕФЕРАЛЛОВ
}


def format_money(value: float) -> str:
    """50054 -> '50 054 ₽' (разделитель тысяч — обычный пробел)."""
    return f"{round(value):,}".replace(",", " ") + " ₽"


def format_int(value: int) -> str:
    return f"{value:,}".replace(",", " ")


def _load_font(size: int) -> ImageFont.FreeTypeFont:
    try:
        return ImageFont.truetype(str(FONT_PATH), size)
    except OSError:
        # Фолбэк, чтобы не падать, если шрифт ещё не положен в /fonts.
        return ImageFont.load_default()


def _fit_font_for_box(
    draw: ImageDraw.ImageDraw,
    text: str,
    box: tuple[int, int, int, int],
    start_size: int = FONT_SIZE,
    min_size: int = MIN_FONT_SIZE,
) -> ImageFont.FreeTypeFont:
    """Подбирает размер шрифта так, чтобы текст влез по ширине рамки."""
    x0, _, x1, _ = box
    max_width = (x1 - x0) - BOX_PADDING_X * 2

    size = start_size
    font = _load_font(size)
    while size > min_size:
        if draw.textlength(text, font=font) <= max_width:
            break
        size -= 2
        font = _load_font(size)
    return font


def _draw_centered_text(draw: ImageDraw.ImageDraw, text: str, box: tuple[int, int, int, int]) -> None:
    x0, y0, x1, y1 = box
    cx, cy = (x0 + x1) // 2, (y0 + y1) // 2
    font = _fit_font_for_box(draw, text, box)
    draw.text((cx, cy), text, font=font, fill=TEXT_COLOR, anchor="mm")


def days_in_team(joined_at: str | None) -> int:
    """Считает количество дней с даты регистрации (users.joined_at, ISO-формат)."""
    if not joined_at:
        return 0
    try:
        joined = datetime.datetime.fromisoformat(joined_at)
    except ValueError:
        return 0
    return max((datetime.datetime.utcnow() - joined).days, 0)


def display_nickname(user: dict[str, Any]) -> str:
    """Кастомный ник, если задан, иначе Telegram username, иначе имя."""
    return (
        user.get("nickname")
        or (f"@{user['username']}" if user.get("username") else None)
        or user.get("first_name")
        or "Без ника"
    )


def generate_profile_card(user: dict[str, Any], referrals_count: int) -> io.BytesIO:
    """
    Накладывает данные профиля на assets/profile.png и возвращает готовое
    изображение в io.BytesIO (без сохранения на диск).

    user — словарь, как возвращает database.get_user() (ключи: nickname,
    username, first_name, joined_at, profit, max_profit, ...).
    """
    base = Image.open(TEMPLATE_PATH).convert("RGBA")
    draw = ImageDraw.Draw(base)

    fields = {
        "nickname": display_nickname(user),
        "days": str(days_in_team(user.get("joined_at"))),
        "sum": format_money(user.get("profit") or 0),
        "max": format_money(user.get("max_profit") or 0),
        "refs": format_int(referrals_count),
    }

    for key, text in fields.items():
        _draw_centered_text(draw, text, FIELD_BOXES[key])

    buffer = io.BytesIO()
    base.convert("RGB").save(buffer, format="PNG")
    buffer.seek(0)
    return buffer
