from app import repo
from tests.helpers import add_people, conn_for, create, drawn, people


def saved_page(client, tok):
    client.post(f"/p/{tok}/saved", data={"saved": "on"})
    return client.get(f"/p/{tok}").text


def recipient_of(app, p):
    return repo.get_recipient(conn_for(app), p.id)


def test_shows_recipient_and_their_items(client, app):
    admin = drawn(client, app)
    alex = people(app, admin)["Alex"]
    rec = recipient_of(app, alex)
    client.post(f"/p/{rec.personal_token}/items", data={"text": "Wool hiking socks", "url": "https://example.com/socks"})
    page = saved_page(client, alex.personal_token)
    assert "you&#39;re buying for" in page or "you're buying for" in page
    assert rec.display_name in page
    assert "Wool hiking socks" in page
    assert 'href="https://example.com/socks"' in page


def test_links_rendered_safely(client, app):
    admin = drawn(client, app)
    alex = people(app, admin)["Alex"]
    rec = recipient_of(app, alex)
    client.post(f"/p/{rec.personal_token}/items", data={"text": "Book", "url": "https://example.com/b"})
    page = saved_page(client, alex.personal_token)
    assert 'rel="noopener noreferrer nofollow"' in page
    assert 'target="_blank"' in page


def test_before_draw_message(client, app):
    admin = create(client)
    add_people(client, admin, ["Alex", "Jordan", "Morgan"])
    page = saved_page(client, people(app, admin)["Alex"].personal_token)
    assert "drawn yet" in page


def test_stale_draw_hides_recipient(client, app):
    admin = drawn(client, app)
    alex = people(app, admin)["Alex"]
    add_people(client, admin, ["Taylor"])
    assert recipient_of(app, alex) is None
    page = saved_page(client, alex.personal_token)
    assert "updating the draw" in page
    assert "buying for" not in page


def test_redraw_keeps_links_and_items(client, app):
    admin = drawn(client, app)
    alex = people(app, admin)["Alex"]
    client.post(f"/p/{alex.personal_token}/items", data={"text": "Board game", "url": ""})
    add_people(client, admin, ["Taylor"])
    client.post(admin + "/draw", data={"confirm": "on"})
    page = saved_page(client, alex.personal_token)
    assert "Board game" in page
    assert recipient_of(app, alex) is not None


def test_add_edit_delete_own_item(client, app):
    admin = drawn(client, app)
    alex = people(app, admin)["Alex"]
    tok = alex.personal_token
    r = client.post(f"/p/{tok}/items", data={"text": "Board game", "url": ""})
    assert r.status_code == 303
    item = repo.list_items(conn_for(app), alex.id)[0]
    assert item.url is None
    client.post(f"/p/{tok}/items/{item.id}/edit", data={"text": "Jigsaw puzzle", "url": "http://example.com"})
    item = repo.list_items(conn_for(app), alex.id)[0]
    assert (item.text, item.url) == ("Jigsaw puzzle", "http://example.com")
    client.post(f"/p/{tok}/items/{item.id}/delete")
    assert repo.list_items(conn_for(app), alex.id) == []


def test_cannot_touch_other_persons_item(client, app):
    admin = drawn(client, app)
    ps = people(app, admin)
    client.post(f"/p/{ps['Jordan'].personal_token}/items", data={"text": "Scarf", "url": ""})
    item = repo.list_items(conn_for(app), ps["Jordan"].id)[0]
    r = client.post(f"/p/{ps['Alex'].personal_token}/items/{item.id}/delete")
    assert r.status_code == 404
    r = client.post(f"/p/{ps['Alex'].personal_token}/items/{item.id}/edit", data={"text": "Hacked", "url": ""})
    assert r.status_code == 404
    assert repo.list_items(conn_for(app), ps["Jordan"].id)[0].text == "Scarf"


def test_javascript_url_rejected(client, app):
    admin = drawn(client, app)
    alex = people(app, admin)["Alex"]
    client.post(f"/p/{alex.personal_token}/saved", data={"saved": "on"})
    r = client.post(f"/p/{alex.personal_token}/items", data={"text": "x", "url": "javascript:alert(1)"})
    assert r.status_code == 400
    assert "http" in r.text
    assert repo.list_items(conn_for(app), alex.id) == []


def test_html_escaped(client, app):
    admin = drawn(client, app)
    alex = people(app, admin)["Alex"]
    client.post(f"/p/{alex.personal_token}/items", data={"text": "<script>x</script>", "url": ""})
    page = saved_page(client, alex.personal_token)
    assert "<script>x</script>" not in page
    assert "&lt;script&gt;x&lt;/script&gt;" in page


def test_item_caps(client, app):
    admin = drawn(client, app)
    alex = people(app, admin)["Alex"]
    tok = alex.personal_token
    assert client.post(f"/p/{tok}/items", data={"text": "x" * 301, "url": ""}).status_code == 400
    assert client.post(f"/p/{tok}/items", data={"text": "x", "url": "https://e.com/" + "a" * 2000}).status_code == 400
    c = conn_for(app)
    for i in range(50):
        repo.add_item(c, alex.id, f"Item {i}", None)
    assert client.post(f"/p/{tok}/items", data={"text": "One more", "url": ""}).status_code == 400


def test_url_without_scheme_gets_https(client, app):
    admin = drawn(client, app)
    alex = people(app, admin)["Alex"]
    client.post(f"/p/{alex.personal_token}/items", data={"text": "Mug", "url": "example.com/mug"})
    assert repo.list_items(conn_for(app), alex.id)[0].url == "https://example.com/mug"


def test_reminder_bar_until_saved(client, app):
    admin = drawn(client, app)
    tok = people(app, admin)["Alex"].personal_token
    page = client.get(f"/p/{tok}?later=1").text
    assert "saved your link yet?" in page
    page = saved_page(client, tok)
    assert "saved your link yet?" not in page


def test_date_shown_friendly(client, app):
    admin = drawn(client, app)
    client.post(admin + "/settings", data={"name": "Family Christmas", "exchange_date": "2026-12-24", "price_limit": "$50"})
    tok = people(app, admin)["Alex"].personal_token
    assert "Thu, Dec 24, 2026" in saved_page(client, tok)


def test_save_step_has_one_simple_instruction(client, app):
    from tests.helpers import drawn, people

    admin = drawn(client, app)
    tok = people(app, admin)["Alex"].personal_token
    page = client.get("/p/" + tok).text
    assert "Copy this link with the button" in page
    assert "add it to your Home Screen" in page
    assert "Do at least one" not in page
    assert "data-tip=" not in page
