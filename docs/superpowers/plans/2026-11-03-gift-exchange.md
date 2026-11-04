# Gift Exchange Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A public, no-accounts Secret Santa web app at `apps.graemecrawley.com/gift-exchange`, where every permission comes from a long unguessable link. Live by Friday 2026-11-06.

**Architecture:** One FastAPI service that renders Jinja2 pages on the server, with a little plain JavaScript for Copy, Share and phone-specific tips. Data lives in SQLite (stdlib `sqlite3`) on a Docker volume. Traefik strips the `/gift-exchange` prefix, and the app builds every URL from `request.scope["root_path"]` (env `ROOT_PATH`). The draw is a pure function. Routes are thin wrappers around `repo.py`.

**Tech Stack:** Python 3.11, FastAPI, Jinja2, python-multipart, uvicorn, prometheus-fastapi-instrumentator; pytest and httpx (FastAPI `TestClient`) for tests.

**Spec:** `docs/superpowers/specs/2026-11-03-gift-exchange-design.md` (approved). Read it before any task. Section numbers below (§) refer to it.

## Global Constraints

- **Tokens:** `secrets.token_urlsafe(24)` (192 bits). The admin token is stored only as a SHA-256 hex hash. The personal token and join token are stored as plain text (the organizer must re-copy personal links, §3/§6.2).
- **No real names** in code, tests, fixtures, commits or screenshots. Use only: Alex, Jordan, Morgan, Riley, Sam, Taylor, Casey, Jamie, Quinn, Avery, Drew, Parker.
- **Caps:** exchange name ≤ 80 characters; person name ≤ 40, unique per exchange (case-insensitive); household ≤ 30; price limit is free text ≤ 20; ≤ 100 participants per exchange; wish item text 1–300; item URL ≤ 2000 and must be `http`/`https`; ≤ 50 items per person.
- **Draw:** needs ≥ 3 people. Never self, never the same household, a perfect one-to-one matching. If no draw is possible, show an error and change nothing.
- **The organizer panel never displays assignments or wish lists.**
- **Headers on every response:** `Referrer-Policy: no-referrer`, `X-Robots-Tag: noindex`. On `/a/*` and `/p/*`, also `Cache-Control: no-store`.
- **Tokens never appear in logs.** Redact `/a/<tok>`, `/p/<tok>` and `/j/<tok>` to `/a/***` and so on.
- **No third-party scripts, fonts or analytics.** Use system fonts only.
- **Environment variables:** `GIFT_DB_PATH` (default `./data/gift.db`), `ROOT_PATH` (default `""`, `/gift-exchange` in prod), `TZ=America/Toronto`.
- **Phone-first.** Tap targets ≥ 44px. Every page works at 360px width with no sideways scrolling.
- **Copy text:** use the spec's wording for the organizer warning (§6.1), Save-your-link (§5.2) and the re-draw warning (§4).

## Review Focus

1. **Double-tap on claim, or two people tapping the same name at once.** Exactly one claim wins, and the other person sees "Already claimed". Test in Task 4 (the claim is a conditional `UPDATE … WHERE claimed_at IS NULL`).
2. **A wrong or old token** (after a reset, or a typo) shows a friendly 404 page ("This link isn't valid. Ask your organizer for a new one."), never a stack trace. Test in Task 3 and Task 4.
3. **Re-submitting a form or pressing Back** (Draw twice, adding the same name twice) doesn't create duplicates or crash. Duplicate names are rejected with a message. Test in Task 3.
4. **A wish-list link like `javascript:alert(1)`**, or HTML in any name or item, is rejected or escaped. Test in Task 5.
5. **The app running under `/gift-exchange`.** Every link, form action, redirect and static URL includes the prefix. Test in Task 6 with `ROOT_PATH=/gift-exchange`.

---

## File Structure

```
app/
  __init__.py
  main.py          # create_app(): routers, middleware, static, templates, metrics, /health
  config.py        # Settings from env (db_path, root_path)
  db.py            # connect(path) -> sqlite3.Connection; init_schema(conn)
  tokens.py        # new_token(), hash_token()
  draw.py          # make_draw(); DrawImpossible
  repo.py          # all SQL; dataclasses Exchange, Participant, WishItem
  security.py      # headers middleware, same-origin POST check, log redaction filter
  ratelimit.py     # in-memory sliding-window limiter + client_ip()
  web.py           # shared Jinja2Templates + url helper + 404 page
  routes_home.py   # / and POST /create
  routes_admin.py  # /a/{token}...
  routes_join.py   # /j/{token}...
  routes_person.py # /p/{token}...
  templates/       # base.html, home.html, admin_saved.html, admin.html, join.html,
                   # person_save.html, person.html, not_found.html, _sharebox.html
  static/          # app.css, app.js, icon-192.png, icon-512.png
tests/
  conftest.py      # client fixture with tmp DB
  test_*.py
Dockerfile, requirements.txt, requirements-dev.txt, README.md, LICENSE (MIT), .gitignore
deploy/compose.yml, deploy/dynamic-gift-exchange.yml
```

---

### Task 1: Scaffold, health, headers, test harness

**Files:**
- Create: `app/__init__.py`, `app/main.py`, `app/config.py`, `app/security.py`, `app/web.py`, `app/templates/base.html`, `app/templates/not_found.html`, `app/static/app.css`, `requirements.txt`, `requirements-dev.txt`, `.gitignore`, `README.md`, `LICENSE`, `tests/conftest.py`, `tests/test_app.py`

**Interfaces:**
- Produces: `create_app(db_path: str | None = None, root_path: str | None = None) -> FastAPI` (it stores `app.state.db_path`). `web.templates` (`Jinja2Templates`). `web.render(request, name: str, ctx: dict, status: int = 200)`. `web.url(request, path: str) -> str`, which prefixes `root_path`. `web.not_found(request)`, which renders `not_found.html` with status 404. Test fixture `client` (a `TestClient` on a tmp-path DB) and fixture `app`.

- [ ] **Step 1: Write the failing tests** in `tests/test_app.py`:
  - `test_health`: `GET /health` → 200, `{"status": "ok"}`.
  - `test_security_headers`: `GET /health` has `referrer-policy: no-referrer` and `x-robots-tag: noindex`.
  - `test_no_store_on_private_paths`: `GET /a/nonexistent` → 404 with `cache-control: no-store`, and the body contains "This link isn't valid".
  - `test_metrics`: `GET /metrics` → 200.
- [ ] **Step 2:** Run `pytest -q` and expect FAIL (import error).
- [ ] **Step 3: Implement.** In `security.py`: an `http` middleware that sets the headers (no-store when the path starts with `/a/` or `/p/`), plus a `RedactTokensFilter(logging.Filter)` that rewrites `r"/(a|p|j)/[A-Za-z0-9_-]+"` to `/\1/***` in the log record's args. Attach it to the `uvicorn.access` logger in `create_app`. Add a catch-all 404 handler that renders `not_found.html`. `.gitignore` covers `data/`, `*.db`, `.superpowers/`, `__pycache__/` and `.venv/`. `README.md` is a short public-facing description plus how to run it locally (`uvicorn app.main:app`). `base.html` uses system fonts, a mobile viewport and `app.css`. Expose `app = create_app()` at module level.
- [ ] **Step 4:** Run `pytest -q` and expect PASS.
- [ ] **Step 5: Commit** with `git commit -m "feat: scaffold app with health, metrics, security headers"`.

### Task 2: Tokens, schema, repo core, draw

**Files:**
- Create: `app/tokens.py`, `app/db.py`, `app/repo.py`, `app/draw.py`, `tests/test_draw.py`, `tests/test_repo.py`

**Interfaces:**
- Produces:
  - `tokens.new_token() -> str` and `tokens.hash_token(t: str) -> str` (SHA-256 hex).
  - `db.connect(path) -> sqlite3.Connection`, with `row_factory=sqlite3.Row`, `PRAGMA foreign_keys=ON` and `journal_mode=WAL`. `db.init_schema(conn)` is idempotent.
  - Dataclasses `Exchange(id, name, exchange_date: str|None, price_limit: str|None, join_token, draw_state: Literal['none','current','stale'], admin_link_saved: bool)`, `Participant(id, exchange_id, display_name, household: str|None, personal_token, claimed: bool, link_saved: bool)` and `WishItem(id, participant_id, text, url: str|None)`.
  - `repo.create_exchange(conn, name) -> tuple[Exchange, str]` returns the exchange and the raw admin token. Also `get_exchange_by_admin(conn, raw_token) -> Exchange|None`, `get_exchange_by_join(conn, join_token) -> Exchange|None`, `get_participant_by_token(conn, tok) -> Participant|None`, `list_participants(conn, exchange_id) -> list[Participant]` (ordered by name, case-insensitive) and `get_participant(conn, exchange_id, pid) -> Participant|None`.
  - `class ValidationError(ValueError)`, whose message is user-facing.
  - `draw.make_draw(people: list[tuple[int, str|None]], rng: random.Random | None = None) -> dict[int, int]` maps giver to receiver. It raises `draw.DrawImpossible(message: str)`.

Schema (`init_schema`):
```sql
CREATE TABLE IF NOT EXISTS exchange(id INTEGER PRIMARY KEY, name TEXT NOT NULL, exchange_date TEXT, price_limit TEXT,
  admin_token_hash TEXT NOT NULL UNIQUE, join_token TEXT NOT NULL UNIQUE,
  draw_state TEXT NOT NULL DEFAULT 'none' CHECK(draw_state IN ('none','current','stale')),
  admin_link_saved_at TEXT, created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS participant(id INTEGER PRIMARY KEY, exchange_id INTEGER NOT NULL REFERENCES exchange(id) ON DELETE CASCADE,
  display_name TEXT NOT NULL, household TEXT, personal_token TEXT NOT NULL UNIQUE,
  claimed_at TEXT, link_saved_at TEXT, created_at TEXT NOT NULL,
  UNIQUE(exchange_id, display_name COLLATE NOCASE));
CREATE TABLE IF NOT EXISTS assignment(giver_id INTEGER PRIMARY KEY REFERENCES participant(id) ON DELETE CASCADE,
  receiver_id INTEGER NOT NULL REFERENCES participant(id) ON DELETE CASCADE);
CREATE TABLE IF NOT EXISTS wish_item(id INTEGER PRIMARY KEY, participant_id INTEGER NOT NULL REFERENCES participant(id) ON DELETE CASCADE,
  text TEXT NOT NULL, url TEXT, position INTEGER NOT NULL, created_at TEXT NOT NULL);
```

- [ ] **Step 1: Write the failing draw tests** in `tests/test_draw.py`, each looping over 200 seeds:
  - `test_no_self_and_bijection`: 10 people, no households. The keys and values are each the full id set, and `g != r`.
  - `test_households_respected`: 9 people in households {A:3, B:2, C:2, None:2}. The giver's household never equals the receiver's when neither is None.
  - `test_none_household_is_not_a_group`: 3 people all with household None → succeeds.
  - `test_too_few`: 2 people → raises `DrawImpossible` with "at least 3".
  - `test_impossible_household`: {A:4, B:1, C:1} (6 people, A has more than half) → raises `DrawImpossible` with "Household A".
  - `test_random`: over 50 seeds on 6 people, more than one distinct result.
- [ ] **Step 2:** Run `pytest tests/test_draw.py -q` and expect FAIL.
- [ ] **Step 3: Implement `make_draw`.** First the fast check: if any household's size is more than n/2, raise with "Household {h} has too many people for this group". Then shuffle the givers and backtrack, assigning each giver a random allowed unused receiver. Cap at 10,000 backtracking steps, then raise "Couldn't find a valid draw". Group sizes are ≤ 100, so this is fast.
- [ ] **Step 4: Write the failing repo tests** in `tests/test_repo.py`:
  - `test_create_exchange_hashes_admin_token`: the raw token isn't in any column, and `get_exchange_by_admin(raw)` returns it.
  - `test_wrong_admin_token_returns_none`.
  - `test_tokens_are_long`: `len(raw) >= 32`.
- [ ] **Step 5:** Implement `tokens.py`, `db.py` and the repo functions above. Use ISO UTC timestamps.
- [ ] **Step 6:** Run `pytest -q` and expect PASS.
- [ ] **Step 7: Commit** with `git commit -m "feat: schema, tokens, repo core, constrained draw"`.

### Task 3: Home, create, organizer panel and organizer actions

**Files:**
- Create: `app/routes_home.py`, `app/routes_admin.py`, `app/templates/home.html`, `app/templates/admin_saved.html`, `app/templates/admin.html`, `app/templates/_sharebox.html`, `tests/test_admin.py`
- Modify: `app/repo.py`, `app/main.py`

**Interfaces:**
- Consumes: Task 2 repo and `make_draw`, plus Task 1 `web.*`.
- Produces repo functions, each raising `ValidationError` on bad input:
  - `update_settings(conn, ex_id, name, exchange_date, price_limit)`
  - `add_participant(conn, ex_id, name) -> Participant`, which sets `draw_state='stale'` if it was `'current'`
  - `rename_participant(conn, ex_id, pid, name)`
  - `set_household(conn, ex_id, pid, household|None)`, which marks a current draw stale (households change who's allowed)
  - `remove_participant(conn, ex_id, pid)`, which deletes their assignments and wish items and marks a current draw stale
  - `reset_claim(conn, ex_id, pid) -> Participant`, which issues a new personal token and clears `claimed_at` and `link_saved_at`
  - `run_draw(conn, ex_id)`, which replaces all assignments in one transaction and sets `'current'`
  - `mark_admin_link_saved(conn, ex_id)`
- `_sharebox.html`: a Jinja macro `sharebox(url, copy_label, kind)` that renders the URL, a Copy button, a Share… button (hidden unless the JS enables it) and a tips slot. Task 6 wires up the JS.
- Routes (all POST forms answer with 303 back to `/a/{t}`, carrying a flash message in a query param `?msg=` drawn from a fixed whitelist of keys, never free text):
  - `GET /` and `POST /create` (name) → `/a/{t}`
  - `GET /a/{t}`: shows `admin_saved.html` until the organizer link has been saved, otherwise `admin.html`
  - `POST /a/{t}/saved`
  - `POST /a/{t}/settings`
  - `POST /a/{t}/people` (name)
  - `POST /a/{t}/people/{pid}/rename|household|remove|reset`
  - `POST /a/{t}/draw`

- [ ] **Step 1: Write the failing tests** in `tests/test_admin.py`:
  - `test_create_redirects_to_admin_save_step`: POST `/create` → 303. Following it shows "This is your organizer link. Don't lose it" and the full admin URL.
  - `test_saved_then_panel`: after POST `saved`, GET shows the panel with "Draw names first" and no group link.
  - `test_add_names_no_auto_organizer`: a new exchange has 0 participants. Add Alex and Jordan; both are listed.
  - `test_duplicate_name_rejected`: adding "alex" after "Alex" shows the error and the count stays 1.
  - `test_draw_requires_three`: 2 people → message "at least 3", and `draw_state` stays `'none'`.
  - `test_draw_success_shows_group_link_not_pairs`: 4 people, draw. The page contains `/j/<join_token>`, and the HTML never contains any person's name immediately after the words "buying for" (no assignment leaks). Every person has a "Copy link" entry.
  - `test_add_after_draw_marks_stale`: after the draw, add Taylor → the panel shows the spec's re-draw warning and a Re-draw button. `draw_state == 'stale'`.
  - `test_remove_after_draw_marks_stale_and_deletes_wishes`.
  - `test_reset_claim_changes_token`: the old `/p/<old>` → 404, and the new token works.
  - `test_impossible_household_message`: 4 people with 3 in household A → the draw shows the "Household A" message and changes nothing.
  - `test_double_draw_post_is_safe`: POST draw twice → still a valid bijection, no error.
  - `test_wrong_admin_token_404`.
  - `test_settings_saved_and_shown`: POST settings with date 2026-12-24 and limit "$50" → the panel shows both, and so does `GET /j/<jt>` after the draw. A name of 81 characters is rejected.
- [ ] **Step 2:** Run `pytest tests/test_admin.py -q` and expect FAIL.
- [ ] **Step 3: Implement** the repo functions, the routes and the templates, following mockup screen 4 and §5.4. The tap-a-person actions can be a `<details>` element per person (no JS needed): rename, household, remove (with a confirm checkbox), reset claim, and the personal link sharebox. The panel shows the person's status, "Joined" or "Not yet".
- [ ] **Step 4:** Run `pytest -q` and expect PASS.
- [ ] **Step 5: Commit** with `git commit -m "feat: organizer flow - create, people, households, draw"`.

### Task 4: Group link, claiming and the Save-your-link step

**Files:**
- Create: `app/routes_join.py`, `app/routes_person.py` (GET and save step only), `app/templates/join.html`, `app/templates/person_save.html`, `tests/test_join.py`
- Modify: `app/repo.py`

**Interfaces:**
- Produces:
  - `repo.claim(conn, ex_id, pid) -> Participant | None`: a single `UPDATE participant SET claimed_at=? WHERE id=? AND exchange_id=? AND claimed_at IS NULL`. It returns `None` if 0 rows changed.
  - `repo.claim_by_token(conn, participant) -> None`: claims on the first open of a personal link (§6.2a). It's a no-op if already claimed.
  - `repo.mark_link_saved(conn, pid)`
- Routes:
  - `GET /j/{jt}`: before the draw it shows "Names haven't been drawn yet. Check back soon." After it, the list of names with claimed ones disabled.
  - `POST /j/{jt}/claim/{pid}` → 303 `/p/{personal_token}`. If already claimed → 409, re-rendering `join.html` with "Already claimed".
  - `GET /p/{pt}`: claims by token, then shows `person_save.html` if the link isn't saved yet, otherwise the person page (Task 5).
  - `POST /p/{pt}/saved` (requires checkbox `saved=on`) → 303 `/p/{pt}`.
  - `POST /p/{pt}/later` → 303 `/p/{pt}?later=1`, which skips the save step for this view only. The reminder bar then shows on the person page. *(Plan's call: there's a small "Remind me later" link under the Continue button, so the reminder bar from §5.3 has a purpose and nobody is ever stuck.)*

- [ ] **Step 1: Write the failing tests** in `tests/test_join.py`:
  - `test_join_before_draw_shows_wait`.
  - `test_join_lists_names_claimed_disabled`.
  - `test_claim_redirects_to_personal_and_shows_save_step`: the page has "Save your personal link now", the full `/p/` URL, and the checkbox "I've saved my link".
  - `test_second_claim_same_name_409`.
  - `test_claim_is_atomic`: call `repo.claim` twice → the first returns a Participant, the second `None`.
  - `test_opening_personal_link_counts_as_claim`: an unclaimed participant's `GET /p/<tok>` → the admin panel shows "Joined".
  - `test_save_requires_checkbox`: POST `saved` without `saved=on` → stays on the save step.
  - `test_one_device_many_claims_allowed`: claim three different names in a row from one client → all succeed.
  - `test_bad_join_token_404`.
- [ ] **Step 2:** Run the tests and expect FAIL.
- [ ] **Step 3: Implement** following mockup screens 1–2 and spec §5.1–5.2, with the footer copy from §5.1.
- [ ] **Step 4:** Run `pytest -q` and expect PASS.
- [ ] **Step 5: Commit** with `git commit -m "feat: group link claiming and save-your-link step"`.

### Task 5: Personal page and wish lists

**Files:**
- Create: `app/templates/person.html`, `tests/test_person.py`
- Modify: `app/routes_person.py`, `app/repo.py`

**Interfaces:**
- Produces:
  - `repo.get_recipient(conn, pid) -> Participant | None`, only when `draw_state == 'current'`
  - `repo.list_items(conn, pid) -> list[WishItem]`
  - `repo.add_item(conn, pid, text, url) -> WishItem`
  - `repo.update_item(conn, pid, item_id, text, url)`
  - `repo.delete_item(conn, pid, item_id)`
  - Item ownership is enforced through `pid` in every query. All of these raise `ValidationError` per the Global Constraints caps.
  - `repo.clean_url(raw: str) -> str | None` strips whitespace, returns `None` for empty input, and raises unless the scheme is http or https.
- Routes: `POST /p/{pt}/items`, `POST /p/{pt}/items/{iid}/edit` and `POST /p/{pt}/items/{iid}/delete`, all → 303 `/p/{pt}`.

- [ ] **Step 1: Write the failing tests** in `tests/test_person.py`:
  - `test_shows_recipient_and_their_items`: after the draw, the page has "you're buying for" plus the recipient's name and their item text and link.
  - `test_links_rendered_safely`: the anchor has `rel="noopener noreferrer nofollow"` and `target="_blank"`.
  - `test_before_draw_message`: "Names haven't been drawn yet".
  - `test_stale_draw_hides_recipient`: after an add-after-draw → "The organizer is updating the draw, check back soon", and no recipient name.
  - `test_redraw_keeps_links_and_items`: re-draw → the same `/p/` tokens still work and items are still present.
  - `test_add_edit_delete_own_item`.
  - `test_cannot_touch_other_persons_item`: deleting someone else's item id through your own token → 404, and the item is untouched.
  - `test_javascript_url_rejected`: `url="javascript:alert(1)"` → error shown, no item created.
  - `test_html_escaped`: item text `<script>x</script>` appears escaped.
  - `test_item_caps`: text of 301 characters is rejected; the 51st item is rejected.
  - `test_reminder_bar_until_saved`: viewed with `?later=1`, the page shows "Haven't saved your link yet?". After `saved`, it doesn't.
- [ ] **Step 2:** Run the tests and expect FAIL.
- [ ] **Step 3: Implement** following mockup screen 3 and spec §5.3 and §7. Editing is a `<details>` per item containing a small form.
- [ ] **Step 4:** Run `pytest -q` and expect PASS.
- [ ] **Step 5: Commit** with `git commit -m "feat: personal page with recipient and wish lists"`.

### Task 6: Copy, Share, Home Screen tips, manifest and the prefix check

**Files:**
- Create: `app/static/app.js`, `app/static/icon-192.png`, `app/static/icon-512.png` (a simple generated gift-box glyph, no third-party art), `tests/test_prefix.py`
- Modify: `app/templates/_sharebox.html`, `app/templates/base.html`, `app/routes_admin.py`, `app/routes_person.py`

**Interfaces:**
- Produces:
  - `GET /a/{t}/manifest.webmanifest` and `GET /p/{t}/manifest.webmanifest`, returning `application/manifest+json` with `name` set to the exchange name, `start_url` and `scope` set to the absolute prefixed page URL, `display: "standalone"`, and the icons.
  - `base.html` emits `<link rel="manifest">` only when the template passes `manifest_url`. Also `apple-mobile-web-app-capable` and `apple-touch-icon`.
- `app.js` (no dependencies):
  - `[data-copy]` buttons use `navigator.clipboard.writeText`, with a select-text fallback, and show "Copied!" for 2 seconds.
  - `[data-share]` buttons are unhidden only if `navigator.share` exists, and call it with `{title, url}`.
  - `[data-tips]` shows the iPhone tip if `/iPhone|iPad/` matches the user agent (or `navigator.platform === 'MacIntel' && maxTouchPoints > 1`), the Android tip if `/Android/` matches, otherwise nothing.
  - The tip copy is exactly as in §6.5.
  - The checkbox gate enables Continue only when ticked. The server still enforces it.

- [ ] **Step 1: Write the failing tests:**
  - `test_person_manifest_start_url`: under `create_app(root_path="/gift-exchange")`, the manifest's `start_url` ends with `/gift-exchange/p/<tok>`.
  - `test_prefix_everywhere`: with `root_path="/gift-exchange"`, go through create → add 3 → draw → join → claim → add item. Every `href=`, `action=` and `src=` that starts with `/` in every page starts with `/gift-exchange/`, and every redirect `Location` starts with `/gift-exchange/`.
  - `test_share_buttons_present_next_to_copy`: on the admin and person pages, each `data-copy` has a sibling `data-share`.
- [ ] **Step 2:** Run the tests and expect FAIL.
- [ ] **Step 3: Implement.** If the TestClient doesn't pass `root_path` through, set `FastAPI(root_path=...)` from config, and have `web.url()` read `request.scope.get("root_path", "")`.
- [ ] **Step 4:** Run `pytest -q` and expect PASS.
- [ ] **Step 5: Manual phone check.** Run `uvicorn app.main:app --host 0.0.0.0 --port 8077`. On an iPhone (Safari) and an Android phone (Chrome) on the home Wi-Fi: Share opens the system sheet, the right tip shows, and Add to Home Screen from a personal page reopens that page. Record the result in the commit message. If no phone is available, note "manual phone check pending" and continue; it's re-checked after deployment.
- [ ] **Step 6: Commit** with `git commit -m "feat: copy/share buttons, home screen tips, per-page manifest"`.

### Task 7: Abuse protection, same-origin POST check and retention

**Files:**
- Create: `app/ratelimit.py`, `tests/test_security.py`
- Modify: `app/security.py`, `app/main.py`, `app/routes_home.py`, `app/routes_join.py`, `app/routes_person.py`, `app/repo.py`

**Interfaces:**
- Produces:
  - `ratelimit.client_ip(request) -> str` uses `CF-Connecting-IP`, then the first `X-Forwarded-For` entry, then `request.client.host`.
  - `ratelimit.Limiter(limit: int, window_s: int).hit(key: str, now: float | None = None) -> bool` returns False when over the limit.
  - Limits: create 10 per IP per hour; claim 30 per IP per 10 minutes; wish-list writes 120 per IP per 10 minutes. When over: 429 with a friendly page.
  - `security.same_origin_ok(request) -> bool`: for POST, if an `Origin` header is present, its host must equal `X-Forwarded-Host` or `Host`. Otherwise 403.
  - `repo.delete_expired(conn, today: date) -> int` deletes exchanges where `exchange_date + 60 days < today`, or where there's no date and `created_at + 365 days < today`. It runs at startup and every 24 hours in an asyncio background task.
  - The home page states the retention rule (§8).

- [ ] **Step 1: Write the failing tests:**
  - `test_create_rate_limited`: the 11th create from one IP → 429.
  - `test_family_on_one_ip_can_claim_12`: 12 claims from one IP → all OK.
  - `test_cross_origin_post_rejected`: POST with `Origin: https://evil.example` → 403.
  - `test_log_redaction`: a filtered record for `GET /p/abcDEF123` renders as `/p/***`.
  - `test_delete_expired`: three exchanges (date 61 days ago, date 59 days ago, no date created 366 days ago) → the 1st and 3rd are deleted.
- [ ] **Step 2:** Run the tests and expect FAIL.
- [ ] **Step 3:** Implement.
- [ ] **Step 4:** Run `pytest -q` and expect PASS.
- [ ] **Step 5: Commit** with `git commit -m "feat: rate limits, same-origin POST check, data retention"`.

### Task 8: Container, deploy files and onboarding request

**Files:**
- Create: `Dockerfile`, `.dockerignore`, `deploy/compose.yml`, `deploy/dynamic-gift-exchange.yml`
- Modify: `README.md` (a Deploy section)

**Interfaces:**
- Container `gift-exchange` listening on port 8000. Env: `ROOT_PATH=/gift-exchange`, `GIFT_DB_PATH=/data/gift.db`, `TZ=America/Toronto`. Named volume `gift_data:/data`. Network `web`. Labels: `portal.tile=true`, `portal.title=Gift Exchange`, `portal.section=apps`, `portal.url=https://apps.graemecrawley.com/gift-exchange/`, `prometheus.scrape=true`, `prometheus.port=8000`. `restart: unless-stopped`.
- Traefik route modelled exactly on `../agentic-lab/deploy/dynamic-agentic-lab.yml`: `Host(apps.graemecrawley.com) && PathPrefix(/gift-exchange)`, middlewares slash-redirect, strip `/gift-exchange`, then `rate-limit`. Priority 220. Keep the header comment about bind-mounting, not symlinking.
- Dockerfile: `python:3.11-slim`, non-root user, `uvicorn app.main:app --host 0.0.0.0 --port 8000 --proxy-headers --forwarded-allow-ips='*'`.

- [ ] **Step 1:** Write the files.
- [ ] **Step 2: Verify locally (not on the live stack).** Run `docker build -t gift-exchange-test .`, then `docker run --rm -d -p 8078:8000 -e ROOT_PATH=/gift-exchange --name gx-test gift-exchange-test`, then `curl -s localhost:8078/health`. Expect `{"status":"ok"}`. Then `docker stop gx-test`. This is a throwaway local container, not a live service.
- [ ] **Step 3:** Run `docker compose -f deploy/compose.yml config` and expect it to be valid.
- [ ] **Step 4: Commit** with `git commit -m "chore: dockerfile and deploy files"`.
- [ ] **Step 5: Hand-off.** Send the infrastructure session an onboarding request (via SendToProject or the rc/notify mechanism in `AGENT-COMMS.md`): the repo path, the `include:` of `../gift-exchange/deploy/compose.yml`, the bind-mount of the dynamic file, and that the route is `/gift-exchange` with no login needed. Do **not** run docker against the live stack.
- [ ] **Step 6: After infrastructure confirms,** smoke-test `https://apps.graemecrawley.com/gift-exchange/health`, then run the full flow once on a real phone using test names. Delete the test exchange afterwards using a manual SQL `DELETE` through infrastructure, or leave it for the retention job.

### Task 9: Visual pass

**Files:**
- Modify: `app/static/app.css`, `app/templates/*.html`

- [ ] **Step 1:** Optionally ask the UI specialist session (Graeme's offer) to review the four screens against the mockups at https://claude.ai/artifact/54MZ1DuD3AZWwKM19TL7jk. The palette from the mockups: ground `#F7F4EE`, ink `#1F2A24`, accent `#2F6B4F`, warning `#A23B2A`, reminder `#FBEFD9`. Use system serif for headings and system sans for body text.
- [ ] **Step 2: Screenshots** (Playwright) at 360×780 and 1280×800 of home, organizer saved-step, panel, join, save-step and person page, using test names only. Check: no sideways scroll, tap targets ≥ 44px, text contrast ≥ 4.5:1.
- [ ] **Step 3:** Run `pytest -q` and expect PASS (copy assertions still hold).
- [ ] **Step 4: Commit** with `git commit -m "style: visual pass"`.

---

## Order and timing for Friday

Tue–Wed: Tasks 1–5 (core works end to end). Wed evening: Task 8 hand-off to infrastructure with what exists, so routing runs in parallel. Thu: Tasks 6, 7 and 9. Fri: re-deploy and test on phones.

If short of time, cut in the spec's §10 order: `delete_expired` in Task 7, then the manifest in Task 6 (keep the tips), then item edit in Task 5.
