"""
Слой работы с базой данных (SQLite через aiosqlite).
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
    profit REAL DEFAULT 0,
    mentor_id INTEGER,
    banned INTEGER DEFAULT 0,
    nickname TEXT,
    max_profit REAL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS applications (
    app_id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    username TEXT,
    text TEXT,
    status TEXT NOT NULL DEFAULT 'pending',
    reason TEXT,
    created_at TEXT,
    decided_at TEXT
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

CREATE TABLE IF NOT EXISTS mentors (
    mentor_id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    description TEXT DEFAULT '',
    specialization TEXT DEFAULT '',
    profit_percent REAL DEFAULT 0,
    profit_count INTEGER DEFAULT 0,
    telegram_id INTEGER,
    created_at TEXT
);

CREATE TABLE IF NOT EXISTS chat_links (
    chat_link_id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    url TEXT NOT NULL,
    created_at TEXT
);
"""


async def init_db() -> None:
    """Создаёт таблицы и выставляет дефолтные настройки при первом запуске."""
    async with aiosqlite.connect(DB_PATH) as db_conn:
        await db_conn.executescript(SCHEMA)
        await db_conn.commit()

        cursor = await db_conn.execute("SELECT value FROM settings WHERE key = 'group_link'")
        row = await cursor.fetchone()
        if row is None:
            await db_conn.execute(
                "INSERT INTO settings (key, value) VALUES ('group_link', ?)",
                (DEFAULT_GROUP_LINK,),
            )
            await db_conn.commit()

        cursor = await db_conn.execute("PRAGMA table_info(users)")
        columns = [col[1] for col in await cursor.fetchall()]

        if "mentor_id" not in columns:
            await db_conn.execute("ALTER TABLE users ADD COLUMN mentor_id INTEGER")
            await db_conn.commit()

        if "banned" not in columns:
            await db_conn.execute("ALTER TABLE users ADD COLUMN banned INTEGER DEFAULT 0")
            await db_conn.commit()

        if "nickname" not in columns:
            await db_conn.execute("ALTER TABLE users ADD COLUMN nickname TEXT")
            await db_conn.commit()

        if "max_profit" not in columns:
            await db_conn.execute("ALTER TABLE users ADD COLUMN max_profit REAL DEFAULT 0")
            await db_conn.commit()

        cursor = await db_conn.execute("PRAGMA table_info(applications)")
        app_columns = [col[1] for col in await cursor.fetchall()]
        if "decided_at" not in app_columns:
            await db_conn.execute("ALTER TABLE applications ADD COLUMN decided_at TEXT")
            await db_conn.commit()

        cursor = await db_conn.execute("PRAGMA table_info(mentors)")
        mentor_columns = [col[1] for col in await cursor.fetchall()]
        if "telegram_id" not in mentor_columns:
            await db_conn.execute("ALTER TABLE mentors ADD COLUMN telegram_id INTEGER")
            await db_conn.commit()


def _row_to_dict(cursor: aiosqlite.Cursor, row: aiosqlite.Row) -> dict[str, Any]:
    return {col[0]: row[i] for i, col in enumerate(cursor.description)}


# ---------------------------------------------------------------------------
# Пользователи
# ---------------------------------------------------------------------------

async def user_exists(user_id: int) -> bool:
    async with aiosqlite.connect(DB_PATH) as db_conn:
        cursor = await db_conn.execute("SELECT 1 FROM users WHERE user_id = ?", (user_id,))
        return await cursor.fetchone() is not None


async def add_user(
    user_id: int,
    username: Optional[str],
    first_name: Optional[str],
    referrer_id: Optional[int],
) -> None:
    joined_at = datetime.datetime.utcnow().isoformat()
    async with aiosqlite.connect(DB_PATH) as db_conn:
        await db_conn.execute(
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
        await db_conn.commit()


async def get_user(user_id: int) -> Optional[dict[str, Any]]:
    async with aiosqlite.connect(DB_PATH) as db_conn:
        cursor = await db_conn.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
        row = await cursor.fetchone()
        return _row_to_dict(cursor, row) if row else None


async def get_all_user_ids() -> list[int]:
    async with aiosqlite.connect(DB_PATH) as db_conn:
        cursor = await db_conn.execute("SELECT user_id FROM users")
        rows = await cursor.fetchall()
        return [row[0] for row in rows]


async def get_all_users_with_referrers() -> list[dict[str, Any]]:
    async with aiosqlite.connect(DB_PATH) as db_conn:
        cursor = await db_conn.execute(
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
    async with aiosqlite.connect(DB_PATH) as db_conn:
        cursor = await db_conn.execute("SELECT * FROM users WHERE referrer_id = ?", (user_id,))
        rows = await cursor.fetchall()
        return [_row_to_dict(cursor, row) for row in rows]


# ---------------------------------------------------------------------------
# Заявки
# ---------------------------------------------------------------------------

async def create_application(user_id: int, username: Optional[str], text: str) -> int:
    created_at = datetime.datetime.utcnow().isoformat()
    async with aiosqlite.connect(DB_PATH) as db_conn:
        cursor = await db_conn.execute(
            """
            INSERT INTO applications (user_id, username, text, status, created_at)
            VALUES (?, ?, ?, 'pending', ?)
            """,
            (user_id, username, text, created_at),
        )
        await db_conn.commit()
        return cursor.lastrowid


async def get_application(app_id: int) -> Optional[dict[str, Any]]:
    async with aiosqlite.connect(DB_PATH) as db_conn:
        cursor = await db_conn.execute("SELECT * FROM applications WHERE app_id = ?", (app_id,))
        row = await cursor.fetchone()
        return _row_to_dict(cursor, row) if row else None


async def get_pending_applications() -> list[dict[str, Any]]:
    async with aiosqlite.connect(DB_PATH) as db_conn:
        cursor = await db_conn.execute(
            "SELECT * FROM applications WHERE status = 'pending' ORDER BY app_id ASC"
        )
        rows = await cursor.fetchall()
        return [_row_to_dict(cursor, row) for row in rows]


async def get_latest_application(user_id: int) -> Optional[dict[str, Any]]:
    async with aiosqlite.connect(DB_PATH) as db_conn:
        cursor = await db_conn.execute(
            "SELECT * FROM applications WHERE user_id = ? ORDER BY app_id DESC LIMIT 1",
            (user_id,),
        )
        row = await cursor.fetchone()
        return _row_to_dict(cursor, row) if row else None


async def update_application_status(app_id: int, status: str, reason: Optional[str] = None) -> None:
    decided_at = datetime.datetime.utcnow().isoformat()
    async with aiosqlite.connect(DB_PATH) as db_conn:
        await db_conn.execute(
            "UPDATE applications SET status = ?, reason = ?, decided_at = ? WHERE app_id = ?",
            (status, reason, decided_at, app_id),
        )
        await db_conn.commit()


# ---------------------------------------------------------------------------
# Настройки (ключ-значение)
# ---------------------------------------------------------------------------

async def get_setting(key: str, default: Optional[str] = None) -> Optional[str]:
    async with aiosqlite.connect(DB_PATH) as db_conn:
        cursor = await db_conn.execute("SELECT value FROM settings WHERE key = ?", (key,))
        row = await cursor.fetchone()
        return row[0] if row else default


async def set_setting(key: str, value: str) -> None:
    async with aiosqlite.connect(DB_PATH) as db_conn:
        await db_conn.execute(
            """
            INSERT INTO settings (key, value)
            VALUES (?, ?)
            ON CONFLICT(key) DO UPDATE SET value = excluded.value
            """,
            (key, value),
        )
        await db_conn.commit()


async def get_referrals_count(user_id: int) -> int:
    async with aiosqlite.connect(DB_PATH) as db_conn:
        async with db_conn.execute(
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
    created_at = datetime.datetime.utcnow().isoformat(sep=" ", timespec="seconds")
    async with aiosqlite.connect(DB_PATH) as db_conn:
        await db_conn.execute(
            """
            INSERT INTO bot_logs (user_id, username, event_type, content, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (user_id, username, event_type, content, created_at),
        )
        await db_conn.commit()


async def get_recent_logs(limit: int = 50) -> list[dict[str, Any]]:
    async with aiosqlite.connect(DB_PATH) as db_conn:
        cursor = await db_conn.execute(
            "SELECT * FROM bot_logs ORDER BY log_id DESC LIMIT ?", (limit,)
        )
        rows = await cursor.fetchall()
        return [_row_to_dict(cursor, row) for row in rows]


async def add_profit(user_id: int, amount: float):
    """Увеличивает общую сумму профита и, если начисление рекордное, обновляет max_profit."""
    async with aiosqlite.connect(DB_PATH) as db_conn:
        await db_conn.execute(
            "INSERT OR IGNORE INTO users (user_id, profit, max_profit) VALUES (?, 0, 0)",
            (user_id,),
        )
        await db_conn.execute(
            "UPDATE users SET profit = COALESCE(profit, 0) + ? WHERE user_id = ?",
            (amount, user_id),
        )
        await db_conn.execute(
            "UPDATE users SET max_profit = MAX(COALESCE(max_profit, 0), ?) WHERE user_id = ?",
            (amount, user_id),
        )
        await db_conn.commit()


async def set_user_mentor(user_id: int, mentor_id: int) -> None:
    async with aiosqlite.connect(DB_PATH) as db_conn:
        await db_conn.execute("UPDATE users SET mentor_id = ? WHERE user_id = ?", (mentor_id, user_id))
        await db_conn.commit()


async def set_user_nickname(user_id: int, nickname: str) -> None:
    """Сохраняет кастомный ник профиля (не путать с Telegram username)."""
    async with aiosqlite.connect(DB_PATH) as db_conn:
        await db_conn.execute(
            "INSERT OR IGNORE INTO users (user_id, nickname) VALUES (?, ?)", (user_id, nickname)
        )
        await db_conn.execute("UPDATE users SET nickname = ? WHERE user_id = ?", (nickname, user_id))
        await db_conn.commit()


# ---------------------------------------------------------------------------
# Наставники
# ---------------------------------------------------------------------------

async def create_mentor(
    name: str,
    description: str,
    specialization: str,
    profit_percent: float,
    profit_count: int,
    telegram_id: Optional[int] = None,
) -> int:
    created_at = datetime.datetime.utcnow().isoformat()
    async with aiosqlite.connect(DB_PATH) as db_conn:
        cursor = await db_conn.execute(
            """
            INSERT INTO mentors (name, description, specialization, profit_percent, profit_count, telegram_id, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (name, description, specialization, profit_percent, profit_count, telegram_id, created_at),
        )
        await db_conn.commit()
        return cursor.lastrowid


async def get_mentor(mentor_id: int) -> Optional[dict[str, Any]]:
    async with aiosqlite.connect(DB_PATH) as db_conn:
        cursor = await db_conn.execute("SELECT * FROM mentors WHERE mentor_id = ?", (mentor_id,))
        row = await cursor.fetchone()
        return _row_to_dict(cursor, row) if row else None


async def get_all_mentors() -> list[dict[str, Any]]:
    async with aiosqlite.connect(DB_PATH) as db_conn:
        cursor = await db_conn.execute("SELECT * FROM mentors ORDER BY mentor_id ASC")
        rows = await cursor.fetchall()
        return [_row_to_dict(cursor, row) for row in rows]


async def update_mentor_description(mentor_id: int, description: str) -> None:
    async with aiosqlite.connect(DB_PATH) as db_conn:
        await db_conn.execute(
            "UPDATE mentors SET description = ? WHERE mentor_id = ?", (description, mentor_id)
        )
        await db_conn.commit()


async def update_mentor_specialization(mentor_id: int, specialization: str) -> None:
    async with aiosqlite.connect(DB_PATH) as db_conn:
        await db_conn.execute(
            "UPDATE mentors SET specialization = ? WHERE mentor_id = ?", (specialization, mentor_id)
        )
        await db_conn.commit()


async def update_mentor_conditions(mentor_id: int, profit_percent: float, profit_count: int) -> None:
    async with aiosqlite.connect(DB_PATH) as db_conn:
        await db_conn.execute(
            "UPDATE mentors SET profit_percent = ?, profit_count = ? WHERE mentor_id = ?",
            (profit_percent, profit_count, mentor_id),
        )
        await db_conn.commit()


async def update_mentor_telegram_id(mentor_id: int, telegram_id: Optional[int]) -> None:
    async with aiosqlite.connect(DB_PATH) as db_conn:
        await db_conn.execute(
            "UPDATE mentors SET telegram_id = ? WHERE mentor_id = ?", (telegram_id, mentor_id)
        )
        await db_conn.commit()


async def delete_mentor(mentor_id: int) -> None:
    async with aiosqlite.connect(DB_PATH) as db_conn:
        await db_conn.execute("UPDATE users SET mentor_id = NULL WHERE mentor_id = ?", (mentor_id,))
        await db_conn.execute("DELETE FROM mentors WHERE mentor_id = ?", (mentor_id,))
        await db_conn.commit()


# ---------------------------------------------------------------------------
# Бан пользователей
# ---------------------------------------------------------------------------

async def is_user_banned(user_id: int) -> bool:
    async with aiosqlite.connect(DB_PATH) as db_conn:
        cursor = await db_conn.execute("SELECT banned FROM users WHERE user_id = ?", (user_id,))
        row = await cursor.fetchone()
        return bool(row[0]) if row else False


async def set_user_banned(user_id: int, banned: bool) -> None:
    async with aiosqlite.connect(DB_PATH) as db_conn:
        await db_conn.execute("INSERT OR IGNORE INTO users (user_id, banned) VALUES (?, 0)", (user_id,))
        await db_conn.execute(
            "UPDATE users SET banned = ? WHERE user_id = ?", (1 if banned else 0, user_id)
        )
        await db_conn.commit()


# ---------------------------------------------------------------------------
# Чаты (раздел «💬 Чаты» в меню — ссылки настраиваются админом)
# ---------------------------------------------------------------------------

async def create_chat_link(title: str, url: str) -> int:
    created_at = datetime.datetime.utcnow().isoformat()
    async with aiosqlite.connect(DB_PATH) as db_conn:
        cursor = await db_conn.execute(
            "INSERT INTO chat_links (title, url, created_at) VALUES (?, ?, ?)",
            (title, url, created_at),
        )
        await db_conn.commit()
        return cursor.lastrowid


async def get_all_chat_links() -> list[dict[str, Any]]:
    async with aiosqlite.connect(DB_PATH) as db_conn:
        cursor = await db_conn.execute("SELECT * FROM chat_links ORDER BY chat_link_id ASC")
        rows = await cursor.fetchall()
        return [_row_to_dict(cursor, row) for row in rows]


async def delete_chat_link(chat_link_id: int) -> None:
    async with aiosqlite.connect(DB_PATH) as db_conn:
        await db_conn.execute("DELETE FROM chat_links WHERE chat_link_id = ?", (chat_link_id,))
        await db_conn.commit()
