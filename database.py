"""Camada de dados (SQLite assíncrono)."""
import asyncio
import datetime as dt
import os

import aiosqlite

DEFAULTS = {
    "module.moderation": "1",
    "module.automod": "1",
    "module.welcome": "1",
    "module.tickets": "1",
    "welcome_message": "Olá, {user}! Bem-vindo(a) ao **{server}**. Você é o membro nº {count}.",
    "ticket_categories": "Suporte,Denúncia,Dúvidas",
    "spam_limit": "5",
    "spam_window": "5",
    "mention_limit": "5",
    "block_links": "0",
    "allowed_domains": "",
    "raid_limit": "8",
    "raid_window": "10",
    "raid_timeout": "0",
}

SCHEMA = """
CREATE TABLE IF NOT EXISTS settings (
    guild_id INTEGER NOT NULL,
    key TEXT NOT NULL,
    value TEXT,
    PRIMARY KEY (guild_id, key)
);
CREATE TABLE IF NOT EXISTS cases (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    guild_id INTEGER NOT NULL,
    case_number INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    moderator_id INTEGER NOT NULL,
    action TEXT NOT NULL,
    reason TEXT,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_cases_user ON cases (guild_id, user_id);
CREATE TABLE IF NOT EXISTS tickets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    guild_id INTEGER NOT NULL,
    channel_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    category TEXT,
    claimed_by INTEGER,
    status TEXT NOT NULL DEFAULT 'open',
    created_at TEXT NOT NULL,
    closed_at TEXT,
    closed_by INTEGER
);
CREATE TABLE IF NOT EXISTS config_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    guild_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    key TEXT NOT NULL,
    old_value TEXT,
    new_value TEXT,
    created_at TEXT NOT NULL
);
"""


def now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")


class Database:
    def __init__(self, path: str):
        self.path = path
        self.conn: aiosqlite.Connection | None = None
        self._lock = asyncio.Lock()

    async def connect(self):
        folder = os.path.dirname(self.path)
        if folder:
            os.makedirs(folder, exist_ok=True)
        self.conn = await aiosqlite.connect(self.path)
        self.conn.row_factory = aiosqlite.Row
        await self.conn.executescript(SCHEMA)
        await self.conn.commit()

    async def close(self):
        if self.conn:
            await self.conn.close()

    async def _one(self, sql, params=()):
        async with self.conn.execute(sql, params) as cur:
            return await cur.fetchone()

    async def _all(self, sql, params=()):
        async with self.conn.execute(sql, params) as cur:
            return await cur.fetchall()

    async def _exec(self, sql, params=()):
        async with self._lock:
            cur = await self.conn.execute(sql, params)
            await self.conn.commit()
            return cur

    # ---------- configurações ----------
    async def get_setting(self, guild_id: int, key: str, default=None):
        row = await self._one(
            "SELECT value FROM settings WHERE guild_id=? AND key=?", (guild_id, key)
        )
        if row is not None and row["value"] is not None:
            return row["value"]
        return DEFAULTS.get(key, default)

    async def get_int(self, guild_id: int, key: str) -> int | None:
        value = await self.get_setting(guild_id, key)
        try:
            return int(value) if value not in (None, "") else None
        except ValueError:
            return None

    async def set_setting(self, guild_id: int, key: str, value: str):
        await self._exec(
            "INSERT INTO settings (guild_id, key, value) VALUES (?,?,?) "
            "ON CONFLICT(guild_id, key) DO UPDATE SET value=excluded.value",
            (guild_id, key, value),
        )

    async def all_settings(self, guild_id: int) -> dict:
        rows = await self._all("SELECT key, value FROM settings WHERE guild_id=?", (guild_id,))
        data = dict(DEFAULTS)
        data.update({r["key"]: r["value"] for r in rows})
        return data

    async def add_history(self, guild_id, user_id, key, old, new):
        await self._exec(
            "INSERT INTO config_history (guild_id,user_id,key,old_value,new_value,created_at) "
            "VALUES (?,?,?,?,?,?)",
            (guild_id, user_id, key, old, new, now()),
        )

    async def get_history(self, guild_id: int, limit: int = 10):
        return await self._all(
            "SELECT * FROM config_history WHERE guild_id=? ORDER BY id DESC LIMIT ?",
            (guild_id, limit),
        )

    # ---------- casos de moderação ----------
    async def add_case(self, guild_id, user_id, moderator_id, action, reason) -> int:
        async with self._lock:
            row = await self._one(
                "SELECT COALESCE(MAX(case_number),0)+1 AS n FROM cases WHERE guild_id=?",
                (guild_id,),
            )
            number = row["n"]
            await self.conn.execute(
                "INSERT INTO cases (guild_id,case_number,user_id,moderator_id,action,reason,created_at) "
                "VALUES (?,?,?,?,?,?,?)",
                (guild_id, number, user_id, moderator_id, action, reason, now()),
            )
            await self.conn.commit()
            return number

    async def get_case(self, guild_id: int, number: int):
        return await self._one(
            "SELECT * FROM cases WHERE guild_id=? AND case_number=?", (guild_id, number)
        )

    async def get_cases(self, guild_id, user_id, action=None, limit=10):
        if action:
            return await self._all(
                "SELECT * FROM cases WHERE guild_id=? AND user_id=? AND action=? "
                "ORDER BY id DESC LIMIT ?",
                (guild_id, user_id, action, limit),
            )
        return await self._all(
            "SELECT * FROM cases WHERE guild_id=? AND user_id=? ORDER BY id DESC LIMIT ?",
            (guild_id, user_id, limit),
        )

    # ---------- tickets ----------
    async def create_ticket(self, guild_id, channel_id, user_id, category) -> int:
        cur = await self._exec(
            "INSERT INTO tickets (guild_id,channel_id,user_id,category,created_at) VALUES (?,?,?,?,?)",
            (guild_id, channel_id, user_id, category, now()),
        )
        return cur.lastrowid

    async def get_open_ticket(self, guild_id, user_id):
        return await self._one(
            "SELECT * FROM tickets WHERE guild_id=? AND user_id=? AND status='open'",
            (guild_id, user_id),
        )

    async def get_ticket_by_channel(self, channel_id):
        return await self._one(
            "SELECT * FROM tickets WHERE channel_id=? AND status='open'", (channel_id,)
        )

    async def claim_ticket(self, ticket_id, staff_id):
        await self._exec("UPDATE tickets SET claimed_by=? WHERE id=?", (staff_id, ticket_id))

    async def close_ticket(self, ticket_id, closed_by):
        await self._exec(
            "UPDATE tickets SET status='closed', closed_at=?, closed_by=? WHERE id=?",
            (now(), closed_by, ticket_id),
        )
