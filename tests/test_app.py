def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_security_headers(client):
    r = client.get("/health")
    assert r.headers["referrer-policy"] == "same-origin"
    assert r.headers["x-robots-tag"] == "noindex"


def test_no_store_on_private_paths(client):
    r = client.get("/a/nonexistent")
    assert r.status_code == 404
    assert r.headers["cache-control"] == "no-store"
    assert "This link isn't valid" in r.text


def test_metrics(client):
    assert client.get("/metrics").status_code == 200


def test_public_base_url_used_for_copied_links(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient

    from app.main import create_app

    monkeypatch.setenv("PUBLIC_BASE_URL", "https://apps.example.com/gift-exchange/")
    app = create_app(db_path=str(tmp_path / "b.db"), root_path="/gift-exchange")
    with TestClient(app, follow_redirects=False) as c:
        admin = c.post("/create", data={"name": "X"}).headers["location"][len("/gift-exchange"):]
        page = c.get(admin).text
    assert "https://apps.example.com/gift-exchange/a/" in page
    assert "http://testserver" not in page


def test_static_links_carry_version_so_phones_refetch(client):
    import re

    page = client.get("/").text
    css = re.search(r'href="(/static/app\.css\?v=\w+)"', page)
    js = re.search(r'src="(/static/app\.js\?v=\w+)"', page)
    assert css and js
    assert client.get(css.group(1)).status_code == 200


def test_countdown_wording():
    from datetime import date

    from app.web import countdown

    today = date(2026, 11, 4)
    assert countdown("2026-12-28", today) == "54 days to go"
    assert countdown("2026-11-05", today) == "Tomorrow!"
    assert countdown("2026-11-04", today) == "Today!"
    assert countdown("2026-11-01", today) == ""
    assert countdown(None, today) == ""


def test_header_shows_countdown_and_limit(client, app):
    from datetime import date, timedelta

    from tests.helpers import drawn, people

    admin = drawn(client, app)
    soon = (date.today() + timedelta(days=10)).isoformat()
    client.post(admin + "/settings", data={"name": "X", "exchange_date": soon, "price_limit": "$50"})
    page = client.get("/p/" + people(app, admin)["Alex"].personal_token + "?later=1").text
    assert "10 days to go" in page
    assert "Gift limit" in page and "$50" in page
