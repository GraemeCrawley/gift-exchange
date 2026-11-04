import pytest

from app import db, repo


@pytest.fixture
def conn(tmp_path):
    c = db.connect(str(tmp_path / "r.db"))
    db.init_schema(c)
    return c


def test_create_exchange_hashes_admin_token(conn):
    ex, raw = repo.create_exchange(conn, "Family Christmas")
    for row in conn.execute("SELECT * FROM exchange"):
        assert raw not in [str(v) for v in tuple(row)]
    found = repo.get_exchange_by_admin(conn, raw)
    assert found is not None and found.id == ex.id
    assert found.draw_state == "none"


def test_wrong_admin_token_returns_none(conn):
    repo.create_exchange(conn, "Family Christmas")
    assert repo.get_exchange_by_admin(conn, "nope") is None


def test_tokens_are_long(conn):
    ex, raw = repo.create_exchange(conn, "Family Christmas")
    assert len(raw) >= 32
    assert len(ex.join_token) >= 32


def test_init_schema_idempotent(conn):
    db.init_schema(conn)
