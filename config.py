"""
Загрузка конфигурации из .env файла.
"""
import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN: str = os.getenv("BOT_TOKEN", "")
if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN не найден в .env файле!")

_admin_ids_raw = os.getenv("ADMIN_IDS", "")
ADMIN_IDS: list[int] = [
    int(admin_id.strip())
    for admin_id in _admin_ids_raw.split(",")
    if admin_id.strip().isdigit()
]

DEFAULT_GROUP_LINK: str = os.getenv("GROUP_LINK", "Ссылка пока не настроена")

DB_PATH: str = os.getenv("DB_PATH", "bot.db")
