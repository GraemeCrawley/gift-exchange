import logging
from datetime import date, timedelta

from app import ratelimit, repo
from app.security import RedactTokensFilter
from tests.helpers import NAMES, add_people, conn_for, create, exchange_for, people


def test_limiter_window():
    lim = ratelimit.Limiter(2, 60)
    assert lim.hit("ip", now=0)
    assert lim.hit("ip", now=1)
    assert not lim.hit("ip", now=2)
    assert lim.hit("other", now=2)
    assert lim.hit("ip", now=61)


def test_create_rate_limited(client):
    for _ in range(10):
        assert client.post("/create", data={"name": "X"}).status_code == 303
    r = client.post("/create", data={"name": "X"})
    assert r.status_code == 429
    assert "slow down" in r.text.lower()


def test_rate_limit_uses_cloudflare_ip(client):
    for _ in range(10):
        client.post("/create", data={"name": "X"}, headers={"CF-Connecting-IP": "1.1.1.1"})
    r = client.post("/create", data={"name": "X"}, headers={"CF-Connecting-IP": "2.2.2.2"})
    assert r.status_code == 303


def test_family_on_one_ip_can_claim_12(client, app):
    admin = create(client)
    add_people(client, admin, NAMES)
    client.post(admin + "/draw")
    join = "/j/" + exchange_for(app, admin).join_token
    for p in people(app, admin).values():
        assert client.post(f"{join}/claim/{p.id}").status_code == 303


def test_cross_origin_post_rejected(client):
    r = client.post("/create", data={"name": "X"}, headers={"Origin": "https://evil.example"})
    assert r.status_code == 403


def test_same_origin_post_allowed(client):
    r = client.post("/create", data={"name": "X"}, headers={"Origin": "http://testserver"})
    assert r.status_code == 303


def test_forwarded_host_origin_allowed(client):
    r = client.post(
        "/create",
        data={"name": "X"},
        headers={"Origin": "https://apps.example.com", "X-Forwarded-Host": "apps.example.com"},
    )
    assert r.status_code == 303


def test_log_redaction():
    rec = logging.LogRecord("uvicorn.access", logging.INFO, "", 0, '%s - "%s %s HTTP/%s" %d',
                            ("1.2.3.4", "GET", "/p/abcDEF123_-x", "1.1", 200), None)
    RedactTokensFilter().filter(rec)
    assert "/p/***" in rec.getMessage()
    assert "abcDEF123" not in rec.getMessage()


def test_delete_expired(app, client):
    c = conn_for(app)
    today = date(2027, 3, 1)
    old, _ = repo.create_exchange(c, "Old")
    recent, _ = repo.create_exchange(c, "Recent")
    undated, _ = repo.create_exchange(c, "Undated")
    fresh_undated, _ = repo.create_exchange(c, "Fresh")
    c.execute("UPDATE exchange SET exchange_date=? WHERE id=?", ((today - timedelta(days=61)).isoformat(), old.id))
    c.execute("UPDATE exchange SET exchange_date=? WHERE id=?", ((today - timedelta(days=59)).isoformat(), recent.id))
    c.execute("UPDATE exchange SET created_at=? WHERE id=?", ((today - timedelta(days=366)).isoformat() + "T00:00:00+00:00", undated.id))
    c.execute("UPDATE exchange SET created_at=? WHERE id=?", ((today - timedelta(days=10)).isoformat() + "T00:00:00+00:00", fresh_undated.id))
    assert repo.delete_expired(c, today) == 2
    left = {r[0] for r in c.execute("SELECT name FROM exchange")}
    assert left == {"Recent", "Fresh"}
