"""
Слой работы с базой данных (SQLite через aiosqlite).
Все функции открывают короткоживущее соединение на операцию — для нагрузки Telegram-бота этого более чем достаточно и не требует пула соединений.
"""

import datetime
from typing import Any, Optional
import aiosqlite

from config import DB_PATH, DEFAULT_GROUP_LINK

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    username TEXT,
    first_name TEXT,
    referrer_id INTEGER,
    joined_at TEXT,
    profit REAL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS applications (
    app_id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    username TEXT,
    text TEXT,
    status TEXT NOT NULL DEFAULT 'pending',
    reason TEXT,
    created_at TEXT
);

CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT
);

CREATE TABLE IF NOT EXISTS bot_logs (
    log_id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    username TEXT,
    event_type TEXT NOT NULL,
    content TEXT,
    created_at TEXT
);
"""


async def init_db() -> None:
    """Создаёт таблицы и выставляет дефолтные настройки при первом запуске."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.executescript(SCHEMA)
        await db.commit()

        cursor = await db.execute("SELECT value FROM settings WHERE key = 'group_link'")
        row = await cursor.fetchone()
        if row is None:
            await db.execute(
                "INSERT INTO settings (key, value) VALUES ('group_link', ?)",
                (DEFAULT_GROUP_LINK,),
            )
            await db.commit()


def _row_to_dict(cursor: aiosqlite.Cursor, row: aiosqlite.Row) -> dict[str, Any]:
    return {col[0]: row[i] for i, col in enumerate(cursor.description)}


# ---------------------------------------------------------------------------
# Пользователи
# ---------------------------------------------------------------------------


async def user_exists(user_id: int) -> bool:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("SELECT 1 FROM users WHERE user_id = ?", (user_id,))
        return await cursor.fetchone() is not None


async def add_user(
    user_id: int,
    username: Optional[str],
    first_name: Optional[str],
    referrer_id: Optional[int],
) -> None:
    joined_at = datetime.datetime.utcnow().isoformat()
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """
            INSERT INTO users (user_id, username, first_name, referrer_id, joined_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                username = excluded.username,
                first_name = excluded.first_name,
                referrer_id = COALESCE(users.referrer_id, excluded.referrer_id)
            """,
            (user_id, username, first_name, referrer_id, joined_at),
        )
        await db.commit()


async def get_user(user_id: int) -> Optional[dict[str, Any]]:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
        row = await cursor.fetchone()
        return _row_to_dict(cursor, row) if row else None


async def get_all_user_ids() -> list[int]:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("SELECT user_id FROM users")
        rows = await cursor.fetchall()
        return [row[0] for row in rows]


async def get_all_users_with_referrers() -> list[dict[str, Any]]:
    """Возвращает всех пользователей вместе с username их реферера (если есть)."""
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            """
            SELECT u.user_id, u.username, u.referrer_id, r.username as referrer_username
            FROM users u
            LEFT JOIN users r ON u.referrer_id = r.user_id
            ORDER BY u.joined_at DESC
            """
        )
        rows = await cursor.fetchall()
        return [_row_to_dict(cursor, row) for row in rows]


async def get_referrals(user_id: int) -> list[dict[str, Any]]:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "SELECT * FROM users WHERE referrer_id = ?", (user_id,)
        )
        rows = await cursor.fetchall()
        return [_row_to_dict(cursor, row) for row in rows]


# ---------------------------------------------------------------------------
# Заявки
# ---------------------------------------------------------------------------


async def create_application(user_id: int, username: Optional[str], text: str) -> int:
    created_at = datetime.datetime.utcnow().isoformat()
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            """
            INSERT INTO applications (user_id, username, text, status, created_at)
            VALUES (?, ?, ?, 'pending', ?)
            """,
            (user_id, username, text, created_at),
        )
        await db.commit()
        return cursor.lastrowid


async def get_application(app_id: int) -> Optional[dict[str, Any]]:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "SELECT * FROM applications WHERE app_id = ?", (app_id,)
        )
        row = await cursor.fetchone()
        return _row_to_dict(cursor, row) if row else None


async def get_pending_applications() -> list[dict[str, Any]]:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "SELECT * FROM applications WHERE status = 'pending' ORDER BY app_id ASC"
        )
        rows = await cursor.fetchall()
        return [_row_to_dict(cursor, row) for row in rows]


async def update_application_status(
    app_id: int, status: str, reason: Optional[str] = None
) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE applications SET status = ?, reason = ? WHERE app_id = ?",
            (status, reason, app_id),
        )
        await db.commit()


# ---------------------------------------------------------------------------
# Настройки (ключ-значение)
# ---------------------------------------------------------------------------


async def get_setting(key: str, default: Optional[str] = None) -> Optional[str]:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("SELECT value FROM settings WHERE key = ?", (key,))
        row = await cursor.fetchone()
        return row[0] if row else default


async def set_setting(key: str, value: str) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """
            INSERT INTO settings (key, value)
            VALUES (?, ?)
            ON CONFLICT(key) DO UPDATE SET value = excluded.value
            """,
            (key, value),
        )
        await db.commit()


async def get_referrals_count(user_id: int) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT COUNT(*) FROM users WHERE referrer_id = ?", (user_id,)
        ) as cursor:
            result = await cursor.fetchone()
            return result[0] if result else 0


# ---------------------------------------------------------------------------
# Логи действий пользователей
# ---------------------------------------------------------------------------


async def add_log(
    user_id: Optional[int],
    username: Optional[str],
    event_type: str,
    content: Optional[str],
) -> None:
    """Сохраняет одно действие пользователя (сообщение или нажатие кнопки)."""
    created_at = datetime.datetime.utcnow().isoformat(sep=" ", timespec="seconds")
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """
            INSERT INTO bot_logs (user_id, username, event_type, content, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (user_id, username, event_type, content, created_at),
        )
        await db.commit()


async def get_recent_logs(limit: int = 50) -> list[dict[str, Any]]:
    """Возвращает последние действия пользователей, от новых к старым."""
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "SELECT * FROM bot_logs ORDER BY log_id DESC LIMIT ?", (limit,)
        )
        rows = await cursor.fetchall()
        return [_row_to_dict(cursor, row) for row in rows]


async def add_profit(user_id: int, amount: float):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT OR IGNORE INTO users (user_id, profit) VALUES (?, 0)",
            (user_id,),
        )
        await db.execute(
            "UPDATE users SET profit = COALESCE(profit, 0) + ? WHERE user_id = ?",
            (amount, user_id),
        )
        await db.commit()
