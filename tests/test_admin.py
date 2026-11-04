from app import repo
from tests.helpers import NAMES, add_people, conn_for, create, drawn, exchange_for, people


def test_create_redirects_to_admin_save_step(client):
    r = client.post("/create", data={"name": "Family Christmas"})
    assert r.status_code == 303
    admin = r.headers["location"]
    assert admin.startswith("/a/")
    page = client.get(admin).text
    assert "This is your organizer link. Don't lose it" in page
    assert "http://testserver" + admin in page


def test_home_page_has_create_form(client):
    r = client.get("/")
    assert r.status_code == 200
    assert 'action="/create"' in r.text


def test_create_requires_name(client):
    r = client.post("/create", data={"name": "  "})
    assert r.status_code == 400
    assert "be empty" in r.text


def test_saved_then_panel(client):
    admin = create(client)
    page = client.get(admin).text
    assert "Draw names first" in page
    assert "/j/" not in page
    # organizer warning stays on the panel permanently
    assert "This is your organizer link. Don't lose it" in page


def test_save_step_requires_checkbox(client, app):
    r = client.post("/create", data={"name": "Family Christmas"})
    admin = r.headers["location"]
    client.post(admin + "/saved", data={})
    assert not exchange_for(app, admin).admin_link_saved


def test_add_names_no_auto_organizer(client, app):
    admin = create(client)
    assert people(app, admin) == {}
    add_people(client, admin, ["Alex", "Jordan"])
    page = client.get(admin).text
    assert "Alex" in page and "Jordan" in page
    assert set(people(app, admin)) == {"Alex", "Jordan"}


def test_duplicate_name_rejected(client, app):
    admin = create(client)
    add_people(client, admin, ["Alex"])
    r = client.post(admin + "/people", data={"name": "alex"})
    assert r.status_code == 400
    assert "already" in r.text
    assert len(people(app, admin)) == 1


def test_name_too_long_rejected(client, app):
    admin = create(client)
    r = client.post(admin + "/people", data={"name": "x" * 41})
    assert r.status_code == 400
    assert people(app, admin) == {}


def test_draw_requires_three(client, app):
    admin = create(client)
    add_people(client, admin, ["Alex", "Jordan"])
    r = client.post(admin + "/draw")
    assert r.status_code == 400
    assert "at least 3" in r.text
    assert exchange_for(app, admin).draw_state == "none"


def test_draw_success_shows_group_link_not_pairs(client, app):
    admin = drawn(client, app)
    ex = exchange_for(app, admin)
    assert ex.draw_state == "current"
    page = client.get(admin).text
    assert "/j/" + ex.join_token in page
    assert "buying for" not in page
    for p in people(app, admin).values():
        assert "/p/" + p.personal_token in page


def test_add_after_draw_marks_stale(client, app):
    admin = drawn(client, app)
    add_people(client, admin, ["Taylor"])
    assert exchange_for(app, admin).draw_state == "stale"
    page = client.get(admin).text
    assert "Everyone gets a new person. Links and wish lists are kept." in page
    assert "Re-draw" in page


def test_remove_after_draw_marks_stale_and_deletes_wishes(client, app):
    admin = drawn(client, app)
    c = conn_for(app)
    alex = people(app, admin)["Alex"]
    c.execute("INSERT INTO wish_item(participant_id,text,position,created_at) VALUES (?,?,0,'x')", (alex.id, "Board game"))
    r = client.post(f"{admin}/people/{alex.id}/remove", data={"confirm": "on"})
    assert r.status_code == 303
    assert "Alex" not in people(app, admin)
    assert c.execute("SELECT count(*) FROM wish_item").fetchone()[0] == 0
    assert exchange_for(app, admin).draw_state == "stale"


def test_remove_requires_confirm(client, app):
    admin = create(client)
    add_people(client, admin, ["Alex"])
    alex = people(app, admin)["Alex"]
    client.post(f"{admin}/people/{alex.id}/remove", data={})
    assert "Alex" in people(app, admin)


def test_rename_and_household(client, app):
    admin = drawn(client, app)
    alex = people(app, admin)["Alex"]
    client.post(f"{admin}/people/{alex.id}/rename", data={"name": "Avery"})
    assert "Avery" in people(app, admin)
    assert exchange_for(app, admin).draw_state == "current"  # rename keeps the draw
    client.post(f"{admin}/people/{alex.id}/household", data={"household": "A"})
    assert people(app, admin)["Avery"].household == "A"
    assert exchange_for(app, admin).draw_state == "stale"  # households change who's allowed


def test_reset_claim_changes_token(client, app):
    admin = drawn(client, app)
    alex = people(app, admin)["Alex"]
    c = conn_for(app)
    c.execute("UPDATE participant SET claimed_at='x' WHERE id=?", (alex.id,))
    client.post(f"{admin}/people/{alex.id}/reset")
    new = people(app, admin)["Alex"]
    assert new.personal_token != alex.personal_token
    assert not new.claimed
    assert repo.get_participant_by_token(c, alex.personal_token) is None


def test_impossible_household_message(client, app):
    admin = create(client)
    add_people(client, admin, NAMES[:4])
    for n in NAMES[:3]:
        p = people(app, admin)[n]
        client.post(f"{admin}/people/{p.id}/household", data={"household": "A"})
    r = client.post(admin + "/draw")
    assert r.status_code == 400
    assert "Household A" in r.text
    assert exchange_for(app, admin).draw_state == "none"


def test_double_draw_post_is_safe(client, app):
    admin = drawn(client, app)
    c = conn_for(app)
    before = c.execute("SELECT giver_id, receiver_id FROM assignment ORDER BY giver_id").fetchall()
    r = client.post(admin + "/draw")  # e.g. Back + resubmit
    assert r.status_code == 400
    after = c.execute("SELECT giver_id, receiver_id FROM assignment ORDER BY giver_id").fetchall()
    assert [tuple(x) for x in before] == [tuple(x) for x in after]


def test_redraw_requires_confirm(client, app):
    admin = drawn(client, app)
    page = client.get(admin).text
    assert "Everyone gets a new person. Links and wish lists are kept." in page
    assert client.post(admin + "/draw", data={"confirm": "on"}).status_code == 303
    rows = conn_for(app).execute("SELECT receiver_id FROM assignment").fetchall()
    assert len({r[0] for r in rows}) == 4


def test_settings_saved_and_shown(client, app):
    admin = create(client)
    r = client.post(admin + "/settings", data={"name": "Family Christmas", "exchange_date": "2026-12-24", "price_limit": "$50"})
    assert r.status_code == 303
    page = client.get(admin).text
    assert "2026-12-24" in page and "$50" in page
    r = client.post(admin + "/settings", data={"name": "x" * 81, "exchange_date": "", "price_limit": ""})
    assert r.status_code == 400


def test_wrong_admin_token_404(client):
    assert client.get("/a/not-a-real-token").status_code == 404
    assert client.post("/a/not-a-real-token/draw").status_code == 404


def test_participant_cap(client, app):
    admin = create(client)
    c = conn_for(app)
    ex = exchange_for(app, admin)
    for i in range(100):
        repo.add_participant(c, ex.id, f"Person {i}")
    r = client.post(admin + "/people", data={"name": "One more"})
    assert r.status_code == 400


def test_add_returns_to_add_box_with_focus(client):
    admin = create(client)
    r = client.post(admin + "/people", data={"name": "Alex"})
    assert r.headers["location"].endswith("?msg=added#add")
    page = client.get(r.headers["location"].split("#")[0]).text
    add_box = page[page.index('id="add"'):]
    assert "Added." in add_box
    assert 'id="newname" name="name" maxlength="40" placeholder="Add a name" required autofocus' in page


def test_add_error_shown_at_add_box(client):
    admin = create(client)
    client.post(admin + "/people", data={"name": "Alex"})
    page = client.post(admin + "/people", data={"name": "alex"}).text
    add_box = page[page.index('id="add"'):]
    assert 'role="alert"' in add_box
    assert "autofocus" in page


def test_person_change_returns_to_people_list(client, app):
    admin = create(client)
    add_people(client, admin, ["Alex", "Jordan", "Morgan"])
    pid = people(app, admin)["Alex"].id
    r = client.post(f"{admin}/people/{pid}/rename", data={"name": "Alexa"})
    assert r.headers["location"].endswith("?msg=renamed#people")
    page = client.get(r.headers["location"].split("#")[0]).text
    assert "Renamed." in page[page.index('id="people"'):]
    assert "autofocus" not in page
