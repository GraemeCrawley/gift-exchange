from app import repo
from tests.helpers import add_people, conn_for, create, drawn, exchange_for, people


def join_path(app, admin):
    return "/j/" + exchange_for(app, admin).join_token


def test_join_before_draw_shows_wait(client, app):
    admin = create(client)
    add_people(client, admin, ["Alex", "Jordan", "Morgan"])
    page = client.get(join_path(app, admin)).text
    assert "Names haven't been drawn yet" in page or "Names haven&#39;t been drawn yet" in page
    assert "/claim/" not in page


def test_join_lists_names_claimed_disabled(client, app):
    admin = drawn(client, app)
    ps = people(app, admin)
    client.post(f"{join_path(app, admin)}/claim/{ps['Alex'].id}")
    page = client.get(join_path(app, admin)).text
    assert f"/claim/{ps['Jordan'].id}" in page
    assert f"/claim/{ps['Alex'].id}" not in page
    assert "Already claimed" in page


def test_claim_redirects_to_personal_and_shows_save_step(client, app):
    admin = drawn(client, app)
    alex = people(app, admin)["Alex"]
    r = client.post(f"{join_path(app, admin)}/claim/{alex.id}")
    assert r.status_code == 303
    assert r.headers["location"] == "/p/" + alex.personal_token
    page = client.get(r.headers["location"]).text
    assert "Save your personal link now" in page
    assert "http://testserver/p/" + alex.personal_token in page
    assert "saved my link" in page


def test_second_claim_same_name_409(client, app):
    admin = drawn(client, app)
    alex = people(app, admin)["Alex"]
    client.post(f"{join_path(app, admin)}/claim/{alex.id}")
    r = client.post(f"{join_path(app, admin)}/claim/{alex.id}")
    assert r.status_code == 409
    assert "Already claimed" in r.text


def test_claim_is_atomic(client, app):
    admin = drawn(client, app)
    alex = people(app, admin)["Alex"]
    c = conn_for(app)
    assert repo.claim(c, alex.exchange_id, alex.id) is not None
    assert repo.claim(c, alex.exchange_id, alex.id) is None


def test_claim_wrong_exchange_404(client, app):
    a1 = drawn(client, app)
    a2 = drawn(client, app)
    other = people(app, a2)["Alex"]
    assert client.post(f"{join_path(app, a1)}/claim/{other.id}").status_code == 404


def test_opening_personal_link_counts_as_claim(client, app):
    admin = drawn(client, app)
    alex = people(app, admin)["Alex"]
    client.get("/p/" + alex.personal_token)
    assert people(app, admin)["Alex"].claimed


def test_save_requires_checkbox(client, app):
    admin = drawn(client, app)
    tok = people(app, admin)["Alex"].personal_token
    client.post(f"/p/{tok}/saved", data={})
    assert not people(app, admin)["Alex"].link_saved
    client.post(f"/p/{tok}/saved", data={"saved": "on"})
    assert people(app, admin)["Alex"].link_saved


def test_one_device_many_claims_allowed(client, app):
    admin = drawn(client, app)
    for name in ["Alex", "Jordan", "Morgan"]:
        p = people(app, admin)[name]
        assert client.post(f"{join_path(app, admin)}/claim/{p.id}").status_code == 303


def test_bad_join_token_404(client):
    assert client.get("/j/not-real").status_code == 404
    assert client.get("/p/not-real").status_code == 404
