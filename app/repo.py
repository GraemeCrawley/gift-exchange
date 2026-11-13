"""All database access. Functions take a sqlite3 connection (autocommit mode)."""

import re
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
    color: str = "green"


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
        color=row["color"],
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


def create_exchange(conn, name: str, color: str | None = None) -> tuple[Exchange, str]:
    from app.themes import DEFAULT, THEMES

    if color and color not in THEMES:
        raise ValidationError("Pick one of the colours shown.")
    name = _clean_text(name, "Exchange name", 80)
    raw = new_token()
    cur = conn.execute(
        "INSERT INTO exchange(name, admin_token_hash, join_token, created_at, color) VALUES (?,?,?,?,?)",
        (name, hash_token(raw), new_token(), now(), color or DEFAULT),
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


def money(value: str | None) -> str:
    """'50' -> '$50'. Anything that isn't a plain number is shown as typed."""
    value = (value or "").strip()
    return "$" + value if re.fullmatch(r"\d+(\.\d{1,2})?", value) else value


def update_settings(
    conn, ex_id: int, name: str, exchange_date: str | None, price_limit: str | None, color: str | None = None
) -> None:
    from app.themes import THEMES

    if color and color not in THEMES:
        raise ValidationError("Pick one of the colours shown.")
    name = _clean_text(name, "Exchange name", 80)
    date = _clean_date(exchange_date)
    limit = _clean_text(price_limit, "Price limit", 20, required=False)
    if limit:
        limit = money(limit)
    conn.execute(
        "UPDATE exchange SET name=?, exchange_date=?, price_limit=?, color=COALESCE(?, color) WHERE id=?",
        (name, date, limit, color or None, ex_id),
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


def _join_names(names: list[str]) -> str:
    return names[0] if len(names) == 1 else ", ".join(names[:-1]) + " & " + names[-1]


def household_labels(people: list[Participant]) -> dict[int, str]:
    """{person id: "Alex & Jordan"} for everyone in a household, named after its members."""
    groups: dict[str, list[Participant]] = {}
    for p in people:
        if p.household:
            groups.setdefault(p.household, []).append(p)
    return {p.id: _join_names([m.display_name for m in members]) for members in groups.values() for p in members}


def _partition(pairs) -> set[frozenset[int]]:
    groups: dict[str, set[int]] = {}
    for pid, key in pairs:
        if key:
            groups.setdefault(key, set()).add(pid)
    return {frozenset(g) for g in groups.values() if len(g) > 1}


def set_households(conn, ex_id: int, choice: dict[int, str]) -> None:
    """Replace all households. choice maps person id -> any group key ('' = none).
    People left out get no household. A household needs at least 2 people."""
    people = list_participants(conn, ex_id)
    ids = {p.id for p in people}
    for pid, key in choice.items():
        if pid not in ids:
            raise LookupError(pid)
        if len(key) > 20:
            raise ValidationError("Something went wrong with the households. Reload the page and try again.")
    new = _partition(choice.items())
    if new == _partition((p.id, p.household) for p in people):
        return
    stored = {pid: str(n) for n, group in enumerate(sorted(new, key=min), 1) for pid in group}
    with transaction(conn):
        conn.executemany(
            "UPDATE participant SET household=? WHERE id=?", [(stored.get(p.id), p.id) for p in people]
        )
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
            labels = household_labels(people)  # so errors name the people, not a number
            result = make_draw([(p.id, labels.get(p.id)) for p in people])
        except DrawImpossible as e:
            raise ValidationError(e.message) from None
        conn.execute(
            "DELETE FROM assignment WHERE giver_id IN (SELECT id FROM participant WHERE exchange_id=?)", (ex_id,)
        )
        conn.executemany("INSERT INTO assignment(giver_id, receiver_id) VALUES (?,?)", result.items())
        # A re-draw is a fresh start: everyone picks their name again; old personal links stop working.
        for p in people:
            if p.claimed or p.link_saved:
                conn.execute(
                    "UPDATE participant SET personal_token=?, claimed_at=NULL, link_saved_at=NULL WHERE id=?",
                    (new_token(), p.id),
                )
        conn.execute("UPDATE exchange SET draw_state='current' WHERE id=?", (ex_id,))


def mark_admin_link_saved(conn, ex_id: int) -> None:
    conn.execute("UPDATE exchange SET admin_link_saved_at=? WHERE id=?", (now(), ex_id))


def claim(conn, ex_id: int, pid: int) -> Participant | None:
    """Claim a name. Returns None if it was already claimed (or doesn't exist)."""
    cur = conn.execute(
        "UPDATE participant SET claimed_at=? WHERE id=? AND exchange_id=? AND claimed_at IS NULL",
        (now(), pid, ex_id),
    )
    if cur.rowcount == 0:
        return None
    return get_participant(conn, ex_id, pid)


def claim_by_token(conn, participant: Participant) -> None:
    """Opening your personal link for the first time counts as claiming your name."""
    if not participant.claimed:
        claim(conn, participant.exchange_id, participant.id)
        participant.claimed = True


def mark_link_saved(conn, pid: int) -> None:
    conn.execute("UPDATE participant SET link_saved_at=? WHERE id=?", (now(), pid))


MAX_ITEMS = 50


def get_recipient(conn, pid: int) -> Participant | None:
    """Who this person is buying for — only while the draw is current."""
    row = conn.execute(
        """SELECT r.* FROM assignment a
           JOIN participant r ON r.id = a.receiver_id
           JOIN participant g ON g.id = a.giver_id
           JOIN exchange e ON e.id = g.exchange_id
           WHERE a.giver_id=? AND e.draw_state='current'""",
        (pid,),
    ).fetchone()
    return _participant(row)


def _item(row) -> WishItem:
    return WishItem(id=row["id"], participant_id=row["participant_id"], text=row["text"], url=row["url"])


def list_items(conn, pid: int) -> list[WishItem]:
    rows = conn.execute("SELECT * FROM wish_item WHERE participant_id=? ORDER BY position, id", (pid,))
    return [_item(r) for r in rows]


def clean_url(raw: str | None) -> str | None:
    from urllib.parse import urlsplit

    value = (raw or "").strip()
    if not value:
        return None
    if len(value) > 2000:
        raise ValidationError("Link must be 2000 characters or fewer.")
    if "://" not in value and ":" not in value.split("/", 1)[0]:
        value = "https://" + value
    parts = urlsplit(value)
    if parts.scheme.lower() not in ("http", "https") or not parts.netloc:
        raise ValidationError("Links must start with http:// or https://")
    return value


def add_item(conn, pid: int, text: str, url: str | None) -> WishItem:
    text = _clean_text(text, "Wish", 300)
    url = clean_url(url)
    with transaction(conn):
        count, maxpos = conn.execute(
            "SELECT count(*), coalesce(max(position), -1) FROM wish_item WHERE participant_id=?", (pid,)
        ).fetchone()
        if count >= MAX_ITEMS:
            raise ValidationError(f"A wish list can have at most {MAX_ITEMS} items.")
        cur = conn.execute(
            "INSERT INTO wish_item(participant_id, text, url, position, created_at) VALUES (?,?,?,?,?)",
            (pid, text, url, maxpos + 1, now()),
        )
    return _item(conn.execute("SELECT * FROM wish_item WHERE id=?", (cur.lastrowid,)).fetchone())


def _require_item(conn, pid: int, item_id: int) -> None:
    if conn.execute("SELECT 1 FROM wish_item WHERE id=? AND participant_id=?", (item_id, pid)).fetchone() is None:
        raise LookupError(item_id)


def update_item(conn, pid: int, item_id: int, text: str, url: str | None) -> None:
    _require_item(conn, pid, item_id)
    text = _clean_text(text, "Wish", 300)
    url = clean_url(url)
    conn.execute("UPDATE wish_item SET text=?, url=? WHERE id=? AND participant_id=?", (text, url, item_id, pid))


def delete_item(conn, pid: int, item_id: int) -> None:
    _require_item(conn, pid, item_id)
    conn.execute("DELETE FROM wish_item WHERE id=? AND participant_id=?", (item_id, pid))


def delete_expired(conn, today) -> int:
    """Delete exchanges 60 days after their date, or 1 year after creation if undated."""
    from datetime import timedelta

    dated_cutoff = (today - timedelta(days=60)).isoformat()
    undated_cutoff = (today - timedelta(days=365)).isoformat()
    cur = conn.execute(
        """DELETE FROM exchange
           WHERE (exchange_date IS NOT NULL AND exchange_date < ?)
              OR (exchange_date IS NULL AND substr(created_at, 1, 10) < ?)""",
        (dated_cutoff, undated_cutoff),
    )
    return cur.rowcount
