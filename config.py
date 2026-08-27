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

DB_PATH: str = os.getenv("DB_PATH", "/app/data/bot.db")

# Фиксированный каталог специализаций наставников: (ключ_для_бд, подпись на кнопке, подпись в тексте карточки).
# Ключ хранится в БД (mentors.specialization, через запятую).
# Подпись на кнопке — всегда обычный юникод-эмодзи (Telegram-кнопки не поддерживают
# премиум/кастомные эмодзи, там рендерится только plain-текст).
# Подпись в карточке — то, что показывается в тексте сообщения (там премиум-эмодзи работают
# через тег <tg-emoji emoji-id="...">, поддерживается только при parse_mode=HTML).
MENTOR_SPECIALIZATIONS: list[tuple[str, str, str]] = [
    ("rest", "🏖 Отдых", '<tg-emoji emoji-id="5084959154947228499">🏖</tg-emoji> Отдых'),
    ("trade", "📈 Трейд", "📈 Трейд"),
    ("escort", "💎 Эскорт", "💎 Эскорт"),
    ("mreo", "📄 МРЭО", "📄 МРЭО"),
    ("nft", "🖼 NFT", "🖼 NFT"),
]
