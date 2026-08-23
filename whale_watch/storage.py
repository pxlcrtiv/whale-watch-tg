"""SQLite persistence: subscriptions, scanned events (idempotence), the scan
cursor, and per-chat alert rate limiting (anti-spam)."""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from .model import Transfer


def utc_now() -> int:
    return int(datetime.now(timezone.utc).timestamp())


class Storage:
    def __init__(self, db_path: str | Path, *, max_alerts_per_hour: int = 10, min_alert_gap_seconds: int = 5) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.max_alerts_per_hour = max_alerts_per_hour
        self.min_alert_gap_seconds = min_alert_gap_seconds
        self._conn = sqlite3.connect(self.db_path)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._init_schema()

    # ------------------------------------------------------------------ schema
    def _init_schema(self) -> None:
        self._conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS subscriptions (
                chat_id    INTEGER NOT NULL,
                address    TEXT    NOT NULL,
                token      TEXT    NOT NULL DEFAULT '*',
                created_at INTEGER NOT NULL,
                PRIMARY KEY (chat_id, address)
            );
            CREATE TABLE IF NOT EXISTS events (
                tx_hash      TEXT NOT NULL,
                log_index    INTEGER NOT NULL,
                block        INTEGER NOT NULL,
                ts           INTEGER,
                token        TEXT NOT NULL,
                token_address TEXT NOT NULL,
                from_addr    TEXT NOT NULL,
                to_addr      TEXT NOT NULL,
                amount       TEXT NOT NULL,
                value_usd    TEXT,
                PRIMARY KEY (tx_hash, log_index)
            );
            CREATE TABLE IF NOT EXISTS cursors (
                chain      TEXT PRIMARY KEY,
                last_block INTEGER NOT NULL
            );
            CREATE TABLE IF NOT EXISTS alerts (
                chat_id   INTEGER NOT NULL,
                tx_hash   TEXT NOT NULL,
                log_index INTEGER NOT NULL,
                sent_at   INTEGER NOT NULL,
                PRIMARY KEY (chat_id, tx_hash, log_index)
            );
            CREATE TABLE IF NOT EXISTS sent_log (
                chat_id INTEGER NOT NULL,
                sent_at INTEGER NOT NULL
            );
            """
        )
        self._conn.commit()

    def close(self) -> None:
        self._conn.close()

    # ------------------------------------------------------------ subscriptions
    def add_subscription(self, chat_id: int, address: str, token: str = "*") -> bool:
        """Returns True if newly subscribed, False if it already existed."""
        cur = self._conn.execute(
            "INSERT OR IGNORE INTO subscriptions (chat_id, address, token, created_at) VALUES (?, ?, ?, ?)",
            (chat_id, address.lower(), token, utc_now()),
        )
        self._conn.commit()
        return cur.rowcount > 0

    def remove_subscription(self, chat_id: int, address: str) -> bool:
        cur = self._conn.execute(
            "DELETE FROM subscriptions WHERE chat_id = ? AND address = ?",
            (chat_id, address.lower()),
        )
        self._conn.commit()
        return cur.rowcount > 0

    def list_subscriptions(self, chat_id: int | None = None) -> list[dict]:
        if chat_id is None:
            rows = self._conn.execute("SELECT * FROM subscriptions ORDER BY rowid").fetchall()
        else:
            rows = self._conn.execute(
                "SELECT * FROM subscriptions WHERE chat_id = ? ORDER BY rowid", (chat_id,)
            ).fetchall()
        return [dict(r) for r in rows]

    def chats_for_address(self, address: str) -> list[int]:
        rows = self._conn.execute(
            "SELECT DISTINCT chat_id FROM subscriptions WHERE address = ?", (address.lower(),)
        ).fetchall()
        return [r["chat_id"] for r in rows]

    def all_watched_addresses(self) -> set[str]:
        return {r["address"] for r in self._conn.execute("SELECT DISTINCT address FROM subscriptions")}

    # ------------------------------------------------------------------ events
    def record_event(self, transfer: Transfer) -> bool:
        """INSERT OR IGNORE keyed on (tx_hash, log_index) -> idempotent re-scans."""
        cur = self._conn.execute(
            """
            INSERT OR IGNORE INTO events
                (tx_hash, log_index, block, ts, token, token_address, from_addr, to_addr, amount, value_usd)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                transfer.tx_hash,
                transfer.log_index,
                transfer.block,
                transfer.timestamp,
                transfer.token,
                transfer.token_address,
                transfer.from_addr,
                transfer.to_addr,
                str(transfer.amount),
                str(transfer.value_usd) if transfer.value_usd is not None else None,
            ),
        )
        self._conn.commit()
        return cur.rowcount > 0

    def has_event(self, tx_hash: str, log_index: int) -> bool:
        row = self._conn.execute(
            "SELECT 1 FROM events WHERE tx_hash = ? AND log_index = ?", (tx_hash, log_index)
        ).fetchone()
        return row is not None

    def recent_events(self, limit: int = 20) -> list[dict]:
        rows = self._conn.execute("SELECT * FROM events ORDER BY block DESC LIMIT ?", (limit,)).fetchall()
        return [dict(r) for r in rows]

    # ------------------------------------------------------------------- cursor
    def get_cursor(self, chain: str) -> int | None:
        row = self._conn.execute("SELECT last_block FROM cursors WHERE chain = ?", (chain,)).fetchone()
        return row["last_block"] if row else None

    def set_cursor(self, chain: str, last_block: int) -> None:
        self._conn.execute(
            "INSERT INTO cursors (chain, last_block) VALUES (?, ?) "
            "ON CONFLICT(chain) DO UPDATE SET last_block = excluded.last_block",
            (chain, last_block),
        )
        self._conn.commit()

    # -------------------------------------------------------------- rate limits
    def alert_allowed(self, chat_id: int, now: int | None = None) -> tuple[bool, str]:
        """Anti-spam gate: max N alerts/hour per chat + min gap between alerts."""
        now = now or utc_now()
        window_start = now - 3600
        (count,) = self._conn.execute(
            "SELECT COUNT(*) FROM sent_log WHERE chat_id = ? AND sent_at >= ?", (chat_id, window_start)
        ).fetchone()
        if count >= self.max_alerts_per_hour:
            return False, f"hourly limit reached ({self.max_alerts_per_hour}/h)"
        (last_sent,) = self._conn.execute(
            "SELECT MAX(sent_at) FROM sent_log WHERE chat_id = ?", (chat_id,)
        ).fetchone()
        if last_sent is not None and now - last_sent < self.min_alert_gap_seconds:
            return False, f"rate-limited ({self.min_alert_gap_seconds}s gap)"
        return True, "ok"

    def record_alert(self, chat_id: int, transfer: Transfer, now: int | None = None) -> None:
        now = now or utc_now()
        self._conn.execute(
            "INSERT OR IGNORE INTO alerts (chat_id, tx_hash, log_index, sent_at) VALUES (?, ?, ?, ?)",
            (chat_id, transfer.tx_hash, transfer.log_index, now),
        )
        self._conn.execute(
            "INSERT INTO sent_log (chat_id, sent_at) VALUES (?, ?)", (chat_id, now)
        )
        self._conn.commit()

    def alert_seen(self, chat_id: int, transfer: Transfer) -> bool:
        row = self._conn.execute(
            "SELECT 1 FROM alerts WHERE chat_id = ? AND tx_hash = ? AND log_index = ?",
            (chat_id, transfer.tx_hash, transfer.log_index),
        ).fetchone()
        return row is not None

    def counts(self) -> dict:
        subs = self._conn.execute("SELECT COUNT(*) FROM subscriptions").fetchone()[0]
        events = self._conn.execute("SELECT COUNT(*) FROM events").fetchone()[0]
        alerts = self._conn.execute("SELECT COUNT(*) FROM alerts").fetchone()[0]
        cursors = {r["chain"]: r["last_block"] for r in self._conn.execute("SELECT * FROM cursors")}
        return {"subscriptions": subs, "events": events, "alerts": alerts, "cursors": cursors}