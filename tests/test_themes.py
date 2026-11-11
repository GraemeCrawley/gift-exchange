"""Per-exchange colour: page accent, Home Screen icon, organizer icon differs from everyone else's."""

import sqlite3
from pathlib import Path

from app import db
from app.themes import THEMES
from tests.helpers import create, drawn, exchange_for, people

STATIC = Path(__file__).resolve().parent.parent / "app" / "static"


def save(client, admin, color):
    return client.post(
        admin + "/settings", data={"name": "Family Christmas", "exchange_date": "", "price_limit": "", "color": color}
    )


def test_new_exchange_is_green(client, app):
    admin = create(client)
    assert exchange_for(app, admin).color == "green"
    page = client.get(admin).text
    assert 'data-color="green"' in page


def test_organizer_picks_a_colour(client, app):
    admin = create(client)
    assert save(client, admin, "red").status_code == 303
    assert exchange_for(app, admin).color == "red"
    page = client.get(admin).text
    assert 'data-color="red"' in page
    assert 'value="red" checked' in page
    assert f'name="theme-color" content="{THEMES["red"]["primary"]}"' in page


def test_unknown_colour_rejected(client, app):
    admin = create(client)
    assert save(client, admin, "chartreuse").status_code == 400
    assert exchange_for(app, admin).color == "green"


def test_settings_without_colour_keeps_it(client, app):
    admin = create(client)
    save(client, admin, "blue")
    client.post(admin + "/settings", data={"name": "Renamed", "exchange_date": "", "price_limit": ""})
    assert exchange_for(app, admin).color == "blue"


def test_organizer_icon_differs_from_everyone_elses(client, app):
    admin = drawn(client, app)
    save(client, admin, "purple")
    ex = exchange_for(app, admin)
    alex = people(app, admin)["Alex"]
    assert 'rel="apple-touch-icon" href="/static/icons/purple-organizer-180.png?v=' in client.get(admin).text
    member = 'rel="apple-touch-icon" href="/static/icons/purple-member-180.png?v='
    assert member in client.get("/j/" + ex.join_token).text
    assert member in client.get("/p/" + alex.personal_token).text


def test_manifests_use_colour_and_role(client, app):
    admin = drawn(client, app)
    save(client, admin, "gold")
    alex = people(app, admin)["Alex"]
    m = client.get(admin + "/manifest.webmanifest").json()
    assert m["theme_color"] == THEMES["gold"]["primary"]
    assert all("/static/icons/gold-organizer-" in i["src"] for i in m["icons"])
    m = client.get(f"/p/{alex.personal_token}/manifest.webmanifest").json()
    assert all("/static/icons/gold-member-" in i["src"] for i in m["icons"])


def test_every_icon_file_exists():
    for color in THEMES:
        for role in ("member", "organizer"):
            for size in (180, 192, 512):
                assert (STATIC / "icons" / f"{color}-{role}-{size}.png").is_file(), (color, role, size)


def test_old_database_gets_colour_column(tmp_path):
    path = str(tmp_path / "old.db")
    raw = sqlite3.connect(path)
    raw.execute(
        "CREATE TABLE exchange(id INTEGER PRIMARY KEY, name TEXT NOT NULL, exchange_date TEXT, price_limit TEXT,"
        " admin_token_hash TEXT NOT NULL UNIQUE, join_token TEXT NOT NULL UNIQUE,"
        " draw_state TEXT NOT NULL DEFAULT 'none', admin_link_saved_at TEXT, created_at TEXT NOT NULL)"
    )
    raw.execute("INSERT INTO exchange(name, admin_token_hash, join_token, created_at) VALUES ('Old','h','j','now')")
    raw.commit()
    raw.close()
    conn = db.connect(path)
    db.init_schema(conn)
    db.init_schema(conn)  # safe to run twice
    assert conn.execute("SELECT color FROM exchange").fetchone()[0] == "green"


def test_icon_change_changes_version(tmp_path, monkeypatch):
    from app import web

    before = web._static_version()
    icon = Path(web.__file__).parent / "static" / "icons" / "green-member-180.png"
    original = icon.read_bytes()
    try:
        icon.write_bytes(original + b"x")
        assert web._static_version() != before
    finally:
        icon.write_bytes(original)
