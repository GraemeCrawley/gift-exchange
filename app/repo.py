"""All database access. Functions take a sqlite3 connection (autocommit mode)."""

import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Literal

from app.tokens import hash_token, new_token


class ValidationError(ValueError):
    """Message is shown to the person."""


@dataclass
class Exchange:
    id: int
    name: str
    exchange_date: str | None
    price_limit: str | None
    join_token: str
    draw_state: Literal["none", "current", "stale"]
    admin_link_saved: bool


@dataclass
class Participant:
    id: int
    exchange_id: int
    display_name: str
    household: str | None
    personal_token: str
    claimed: bool
    link_saved: bool


@dataclass
class WishItem:
    id: int
    participant_id: int
    text: str
    url: str | None


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@contextmanager
def transaction(conn: sqlite3.Connection):
    conn.execute("BEGIN IMMEDIATE")
    try:
        yield
    except BaseException:
        conn.execute("ROLLBACK")
        raise
    conn.execute("COMMIT")


def _exchange(row) -> Exchange | None:
    if row is None:
        return None
    return Exchange(
        id=row["id"],
        name=row["name"],
        exchange_date=row["exchange_date"],
        price_limit=row["price_limit"],
        join_token=row["join_token"],
        draw_state=row["draw_state"],
        admin_link_saved=row["admin_link_saved_at"] is not None,
    )


def _participant(row) -> Participant | None:
    if row is None:
        return None
    return Participant(
        id=row["id"],
        exchange_id=row["exchange_id"],
        display_name=row["display_name"],
        household=row["household"],
        personal_token=row["personal_token"],
        claimed=row["claimed_at"] is not None,
        link_saved=row["link_saved_at"] is not None,
    )


def _clean_text(value: str | None, label: str, max_len: int, required: bool = True) -> str | None:
    value = (value or "").strip()
    if not value:
        if required:
            raise ValidationError(f"{label} can't be empty.")
        return None
    if len(value) > max_len:
        raise ValidationError(f"{label} must be {max_len} characters or fewer.")
    return value


def create_exchange(conn, name: str) -> tuple[Exchange, str]:
    name = _clean_text(name, "Exchange name", 80)
    raw = new_token()
    cur = conn.execute(
        "INSERT INTO exchange(name, admin_token_hash, join_token, created_at) VALUES (?,?,?,?)",
        (name, hash_token(raw), new_token(), now()),
    )
    return get_exchange(conn, cur.lastrowid), raw


def get_exchange(conn, ex_id: int) -> Exchange | None:
    return _exchange(conn.execute("SELECT * FROM exchange WHERE id=?", (ex_id,)).fetchone())


def get_exchange_by_admin(conn, raw_token: str) -> Exchange | None:
    row = conn.execute("SELECT * FROM exchange WHERE admin_token_hash=?", (hash_token(raw_token),)).fetchone()
    return _exchange(row)


def get_exchange_by_join(conn, join_token: str) -> Exchange | None:
    return _exchange(conn.execute("SELECT * FROM exchange WHERE join_token=?", (join_token,)).fetchone())


def get_participant_by_token(conn, tok: str) -> Participant | None:
    return _participant(conn.execute("SELECT * FROM participant WHERE personal_token=?", (tok,)).fetchone())


def get_participant(conn, exchange_id: int, pid: int) -> Participant | None:
    row = conn.execute("SELECT * FROM participant WHERE id=? AND exchange_id=?", (pid, exchange_id)).fetchone()
    return _participant(row)


def list_participants(conn, exchange_id: int) -> list[Participant]:
    rows = conn.execute(
        "SELECT * FROM participant WHERE exchange_id=? ORDER BY display_name COLLATE NOCASE", (exchange_id,)
    )
    return [_participant(r) for r in rows]
