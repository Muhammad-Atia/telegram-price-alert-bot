"""SQLite storage: alerts survive a restart. One small file, no server."""
from __future__ import annotations

import sqlite3
from decimal import Decimal
from pathlib import Path

from .alerts import Alert

SCHEMA = """CREATE TABLE IF NOT EXISTS alerts (
    id      INTEGER PRIMARY KEY AUTOINCREMENT,
    chat_id INTEGER NOT NULL,
    symbol  TEXT    NOT NULL,
    op      TEXT    NOT NULL CHECK (op IN ('>', '<')),
    price   TEXT    NOT NULL,              -- Decimal as text: no float rounding
    created TEXT    NOT NULL DEFAULT CURRENT_TIMESTAMP
)"""


class Store:
    def __init__(self, path: str | Path):
        if str(path) != ":memory:":
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(path)
        self.db.execute(SCHEMA)
        self.db.commit()

    def add(self, chat_id: int, symbol: str, op: str, price: Decimal) -> Alert:
        cur = self.db.execute("INSERT INTO alerts (chat_id, symbol, op, price) VALUES (?, ?, ?, ?)", (chat_id, symbol, op, str(price)))
        self.db.commit()
        return Alert(cur.lastrowid, chat_id, symbol, op, price)

    def for_chat(self, chat_id: int) -> list[Alert]:
        return [self._row(r) for r in self.db.execute("SELECT id, chat_id, symbol, op, price FROM alerts WHERE chat_id = ? ORDER BY id", (chat_id,))]

    def all(self) -> list[Alert]:
        return [self._row(r) for r in self.db.execute("SELECT id, chat_id, symbol, op, price FROM alerts ORDER BY id")]

    def count(self, chat_id: int) -> int:
        return self.db.execute("SELECT COUNT(*) FROM alerts WHERE chat_id = ?", (chat_id,)).fetchone()[0]

    def remove(self, chat_id: int, alert_id: int) -> bool:
        """Only the chat that created an alert can remove it."""
        cur = self.db.execute("DELETE FROM alerts WHERE id = ? AND chat_id = ?", (alert_id, chat_id))
        self.db.commit()
        return cur.rowcount > 0

    @staticmethod
    def _row(r) -> Alert:
        return Alert(r[0], r[1], r[2], r[3], Decimal(r[4]))
