def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_security_headers(client):
    r = client.get("/health")
    assert r.headers["referrer-policy"] == "no-referrer"
    assert r.headers["x-robots-tag"] == "noindex"


def test_no_store_on_private_paths(client):
    r = client.get("/a/nonexistent")
    assert r.status_code == 404
    assert r.headers["cache-control"] == "no-store"
    assert "This link isn't valid" in r.text


def test_metrics(client):
    assert client.get("/metrics").status_code == 200
