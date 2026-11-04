import re

import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from tests.helpers import NAMES

PREFIX = "/gift-exchange"


@pytest.fixture
def papp(tmp_path):
    return create_app(db_path=str(tmp_path / "p.db"), root_path=PREFIX)


@pytest.fixture
def pclient(papp):
    # Traefik strips the prefix before requests reach the app.
    with TestClient(papp, follow_redirects=False) as c:
        yield c


def strip(location: str) -> str:
    assert location.startswith(PREFIX + "/"), location
    return location[len(PREFIX):]


def local_urls(html: str) -> list[str]:
    return [u for u in re.findall(r'(?:href|action|src)="([^"]+)"', html) if u.startswith("/")]


def test_prefix_everywhere(pclient):
    pages = [pclient.get("/").text]
    r = pclient.post("/create", data={"name": "Family Christmas"})
    admin = strip(r.headers["location"])
    pages.append(pclient.get(admin).text)
    loc = pclient.post(admin + "/saved", data={"saved": "on"}).headers["location"]
    strip(loc)
    for n in NAMES[:3]:
        strip(pclient.post(admin + "/people", data={"name": n}).headers["location"])
    strip(pclient.post(admin + "/draw").headers["location"])
    panel = pclient.get(admin).text
    pages.append(panel)
    join = re.search(r"/j/[A-Za-z0-9_-]+", panel).group(0)
    jpage = pclient.get(join).text
    pages.append(jpage)
    pick = re.search(r'href="' + PREFIX + r'(/j/[^"]+/claim/\d+)"', jpage).group(1)
    cpage = pclient.get(pick).text
    pages.append(cpage)
    claim = re.search(r'action="' + PREFIX + r'(/j/[^"]+/claim/\d+)"', cpage).group(1)
    person = strip(pclient.post(claim).headers["location"])
    pages.append(pclient.get(person).text)
    strip(pclient.post(person + "/saved", data={"saved": "on"}).headers["location"])
    strip(pclient.post(person + "/items", data={"text": "Socks", "url": ""}).headers["location"])
    pages.append(pclient.get(person).text)
    for html in pages:
        for u in local_urls(html):
            assert u.startswith(PREFIX + "/"), u
    assert f"http://testserver{PREFIX}/j/" in panel


def test_person_manifest_start_url(pclient, papp):
    from tests.helpers import conn_for
    from app import repo

    admin = strip(pclient.post("/create", data={"name": "Family Christmas"}).headers["location"])
    pclient.post(admin + "/people", data={"name": "Alex"})
    ex = repo.get_exchange_by_admin(conn_for(papp), admin.rsplit("/", 1)[-1])
    tok = repo.list_participants(conn_for(papp), ex.id)[0].personal_token
    r = pclient.get(f"/p/{tok}/manifest.webmanifest")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("application/manifest+json")
    m = r.json()
    assert m["start_url"].endswith(f"{PREFIX}/p/{tok}")
    assert m["display"] == "standalone"
    assert m["name"] == "Family Christmas"
    page = pclient.get(f"/p/{tok}").text
    assert f'rel="manifest" href="{PREFIX}/p/{tok}/manifest.webmanifest"' in page


def test_admin_manifest(pclient):
    admin = strip(pclient.post("/create", data={"name": "Family Christmas"}).headers["location"])
    m = pclient.get(admin + "/manifest.webmanifest").json()
    assert m["start_url"].endswith(PREFIX + admin)


def test_share_buttons_present_next_to_copy(client):
    from tests.helpers import drawn

    admin = drawn(client, client.app)
    page = client.get(admin).text
    assert page.count("data-copy=") == page.count("data-share=") > 0


def test_static_js_served(pclient):
    r = pclient.get("/static/app.js")
    assert r.status_code == 200
    assert "navigator.share" in r.text
