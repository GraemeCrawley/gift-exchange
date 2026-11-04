"""Shared test helpers. Names are made up; never use real people's names."""

from app import db, repo

NAMES = ["Alex", "Jordan", "Morgan", "Riley", "Sam", "Taylor", "Casey", "Jamie", "Quinn", "Avery", "Drew", "Parker"]


def conn_for(app):
    c = db.connect(app.state.db_path)
    return c


def create(client, name="Family Christmas") -> str:
    """Create an exchange, confirm the organizer link is saved, return the admin path."""
    r = client.post("/create", data={"name": name})
    assert r.status_code == 303
    admin = r.headers["location"]
    client.post(admin + "/saved", data={"saved": "on"})
    return admin


def add_people(client, admin, names):
    for n in names:
        r = client.post(admin + "/people", data={"name": n})
        assert r.status_code == 303, r.text


def exchange_for(app, admin) -> repo.Exchange:
    return repo.get_exchange_by_admin(conn_for(app), admin.rsplit("/", 1)[-1])


def people(app, admin) -> dict[str, repo.Participant]:
    ex = exchange_for(app, admin)
    return {p.display_name: p for p in repo.list_participants(conn_for(app), ex.id)}


def drawn(client, app, names=None) -> str:
    admin = create(client)
    add_people(client, admin, names or NAMES[:4])
    r = client.post(admin + "/draw")
    assert r.status_code == 303
    return admin
