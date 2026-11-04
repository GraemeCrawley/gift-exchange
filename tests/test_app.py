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
