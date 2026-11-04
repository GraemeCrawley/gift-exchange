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


MAX_PARTICIPANTS = 100


def _mark_stale(conn, ex_id: int) -> None:
    conn.execute("UPDATE exchange SET draw_state='stale' WHERE id=? AND draw_state='current'", (ex_id,))


def _clean_date(value: str | None) -> str | None:
    value = (value or "").strip()
    if not value:
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%d").date().isoformat()
    except ValueError:
        raise ValidationError("Exchange date must be a valid date.") from None


def update_settings(conn, ex_id: int, name: str, exchange_date: str | None, price_limit: str | None) -> None:
    name = _clean_text(name, "Exchange name", 80)
    date = _clean_date(exchange_date)
    limit = _clean_text(price_limit, "Price limit", 20, required=False)
    conn.execute(
        "UPDATE exchange SET name=?, exchange_date=?, price_limit=? WHERE id=?", (name, date, limit, ex_id)
    )


def add_participant(conn, ex_id: int, name: str) -> Participant:
    name = _clean_text(name, "Name", 40)
    with transaction(conn):
        count = conn.execute("SELECT count(*) FROM participant WHERE exchange_id=?", (ex_id,)).fetchone()[0]
        if count >= MAX_PARTICIPANTS:
            raise ValidationError(f"An exchange can have at most {MAX_PARTICIPANTS} people.")
        try:
            cur = conn.execute(
                "INSERT INTO participant(exchange_id, display_name, personal_token, created_at) VALUES (?,?,?,?)",
                (ex_id, name, new_token(), now()),
            )
        except sqlite3.IntegrityError:
            raise ValidationError(f"{name} is already in this exchange.") from None
        _mark_stale(conn, ex_id)
    return get_participant(conn, ex_id, cur.lastrowid)


def _require_participant(conn, ex_id: int, pid: int) -> Participant:
    p = get_participant(conn, ex_id, pid)
    if p is None:
        raise LookupError(pid)
    return p


def rename_participant(conn, ex_id: int, pid: int, name: str) -> None:
    _require_participant(conn, ex_id, pid)
    name = _clean_text(name, "Name", 40)
    try:
        conn.execute("UPDATE participant SET display_name=? WHERE id=?", (name, pid))
    except sqlite3.IntegrityError:
        raise ValidationError(f"{name} is already in this exchange.") from None


def set_household(conn, ex_id: int, pid: int, household: str | None) -> None:
    p = _require_participant(conn, ex_id, pid)
    household = _clean_text(household, "Household", 30, required=False)
    if household:
        # Reuse an existing household's spelling so "a" and "A" are the same household.
        row = conn.execute(
            "SELECT household FROM participant WHERE exchange_id=? AND household=? COLLATE NOCASE LIMIT 1",
            (ex_id, household),
        ).fetchone()
        if row:
            household = row["household"]
    if household == p.household:
        return
    with transaction(conn):
        conn.execute("UPDATE participant SET household=? WHERE id=?", (household, pid))
        _mark_stale(conn, ex_id)


def remove_participant(conn, ex_id: int, pid: int) -> None:
    _require_participant(conn, ex_id, pid)
    with transaction(conn):
        conn.execute("DELETE FROM participant WHERE id=?", (pid,))  # cascades to assignments + wish items
        _mark_stale(conn, ex_id)


def reset_claim(conn, ex_id: int, pid: int) -> Participant:
    _require_participant(conn, ex_id, pid)
    conn.execute(
        "UPDATE participant SET personal_token=?, claimed_at=NULL, link_saved_at=NULL WHERE id=?",
        (new_token(), pid),
    )
    return get_participant(conn, ex_id, pid)


def run_draw(conn, ex_id: int) -> None:
    from app.draw import DrawImpossible, make_draw

    with transaction(conn):
        people = list_participants(conn, ex_id)
        try:
            result = make_draw([(p.id, p.household) for p in people])
        except DrawImpossible as e:
            raise ValidationError(e.message) from None
        conn.execute(
            "DELETE FROM assignment WHERE giver_id IN (SELECT id FROM participant WHERE exchange_id=?)", (ex_id,)
        )
        conn.executemany("INSERT INTO assignment(giver_id, receiver_id) VALUES (?,?)", result.items())
        conn.execute("UPDATE exchange SET draw_state='current' WHERE id=?", (ex_id,))


def mark_admin_link_saved(conn, ex_id: int) -> None:
    conn.execute("UPDATE exchange SET admin_link_saved_at=? WHERE id=?", (now(), ex_id))
