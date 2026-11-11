import os
import sqlite3

SCHEMA = """
CREATE TABLE IF NOT EXISTS exchange(
  id INTEGER PRIMARY KEY,
  name TEXT NOT NULL,
  exchange_date TEXT,
  price_limit TEXT,
  admin_token_hash TEXT NOT NULL UNIQUE,
  join_token TEXT NOT NULL UNIQUE,
  draw_state TEXT NOT NULL DEFAULT 'none' CHECK(draw_state IN ('none','current','stale')),
  admin_link_saved_at TEXT,
  created_at TEXT NOT NULL,
  color TEXT NOT NULL DEFAULT 'green');
CREATE TABLE IF NOT EXISTS participant(
  id INTEGER PRIMARY KEY,
  exchange_id INTEGER NOT NULL REFERENCES exchange(id) ON DELETE CASCADE,
  display_name TEXT NOT NULL,
  household TEXT,
  personal_token TEXT NOT NULL UNIQUE,
  claimed_at TEXT,
  link_saved_at TEXT,
  created_at TEXT NOT NULL,
  UNIQUE(exchange_id, display_name COLLATE NOCASE));
CREATE TABLE IF NOT EXISTS assignment(
  giver_id INTEGER PRIMARY KEY REFERENCES participant(id) ON DELETE CASCADE,
  receiver_id INTEGER NOT NULL REFERENCES participant(id) ON DELETE CASCADE);
CREATE TABLE IF NOT EXISTS wish_item(
  id INTEGER PRIMARY KEY,
  participant_id INTEGER NOT NULL REFERENCES participant(id) ON DELETE CASCADE,
  text TEXT NOT NULL,
  url TEXT,
  position INTEGER NOT NULL,
  created_at TEXT NOT NULL);
"""


def connect(path: str) -> sqlite3.Connection:
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    conn = sqlite3.connect(path, isolation_level=None, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=5000")
    conn.execute("PRAGMA synchronous=NORMAL")
    return conn


def init_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA)
    # Databases made before colours existed: add the column.
    cols = {r[1] for r in conn.execute("PRAGMA table_info(exchange)")}
    if "color" not in cols:
        conn.execute("ALTER TABLE exchange ADD COLUMN color TEXT NOT NULL DEFAULT 'green'")
