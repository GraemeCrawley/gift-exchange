from app import repo
from tests.helpers import NAMES, add_people, conn_for, create, drawn, exchange_for, people


def setup(client, names=("Alex", "Jordan", "Morgan", "Riley")):
    admin = create(client)
    add_people(client, admin, list(names))
    return admin


def save(client, admin, groups):
    """groups: {name: key}; '' means no household. ids are looked up by the caller."""
    return client.post(admin + "/households", data=groups)


def form_for(app, admin, mapping):
    ps = people(app, admin)
    return {f"hh_{ps[n].id}": key for n, key in mapping.items()}


def test_page_lists_everyone_and_works_without_script(client, app):
    admin = setup(client)
    page = client.get(admin + "/households").text
    for n in ["Alex", "Jordan", "Morgan", "Riley"]:
        assert n in page
    assert "Add household" in page
    alex = people(app, admin)["Alex"]
    assert f'name="hh_{alex.id}"' in page  # plain dropdowns are the no-script fallback


def test_saving_groups_people(client, app):
    admin = setup(client)
    r = save(client, admin, form_for(app, admin, {"Alex": "1", "Jordan": "1", "Morgan": "", "Riley": ""}))
    assert r.status_code == 303
    assert r.headers["location"].endswith("?msg=household#people")
    ps = people(app, admin)
    assert ps["Alex"].household is not None
    assert ps["Alex"].household == ps["Jordan"].household
    assert ps["Morgan"].household is None


def test_one_person_household_is_dropped(client, app):
    admin = setup(client)
    save(client, admin, form_for(app, admin, {"Alex": "1", "Jordan": "2", "Morgan": "2", "Riley": ""}))
    ps = people(app, admin)
    assert ps["Alex"].household is None
    assert ps["Jordan"].household == ps["Morgan"].household is not None


def test_existing_households_shown_on_page(client, app):
    admin = setup(client)
    save(client, admin, form_for(app, admin, {"Alex": "1", "Jordan": "1"}))
    page = client.get(admin + "/households").text
    assert "Alex &amp; Jordan" in page


def test_admin_tag_names_the_members(client, app):
    admin = setup(client)
    save(client, admin, form_for(app, admin, {"Alex": "a", "Jordan": "a", "Morgan": "a"}))
    page = client.get(admin).text
    assert "Alex, Jordan &amp; Morgan" in page
    assert "/households" in page
    assert "Household (optional)" not in page


def test_same_groups_keep_the_draw(client, app):
    admin = drawn(client, app)
    save(client, admin, form_for(app, admin, {n: "" for n in NAMES[:4]}))
    assert exchange_for(app, admin).draw_state == "current"
    save(client, admin, form_for(app, admin, {"Alex": "1", "Jordan": "1"}))
    assert exchange_for(app, admin).draw_state == "stale"


def test_person_from_other_exchange_is_404(client, app):
    a1 = setup(client)
    a2 = setup(client)
    other = people(app, a2)["Alex"]
    assert client.post(a1 + "/households", data={f"hh_{other.id}": "1"}).status_code == 404


def test_too_big_household_message_names_people(client, app):
    admin = setup(client)
    save(client, admin, form_for(app, admin, {"Alex": "1", "Jordan": "1", "Morgan": "1"}))
    r = client.post(admin + "/draw")
    assert r.status_code == 400
    assert "Alex, Jordan &amp; Morgan" in r.text


def test_repo_set_households_partition(app, client):
    admin = setup(client)
    c = conn_for(app)
    ps = people(app, admin)
    ex = exchange_for(app, admin)
    repo.set_households(c, ex.id, {ps["Alex"].id: "x", ps["Riley"].id: "x"})
    assert repo.household_labels(repo.list_participants(c, ex.id))[ps["Alex"].id] == "Alex & Riley"
