# Gift Exchange — Design

Date: 2026-11-03
Status: approved by Graeme 2026-11-03
Deadline: live by **Friday 2026-11-06** for the two family exchanges (see §10)
Mockups: https://claude.ai/artifact/54MZ1DuD3AZWwKM19TL7jk (private canvas, 4 phone screens)

## 1. What this is and why

A public, no-accounts Secret Santa web app. Anyone can create a gift exchange.
There are no accounts, passwords, or email: every capability is a long,
unguessable link.

The first real use is two family exchanges this Christmas (one with Graeme's
mom and his siblings, one with his dad and his siblings), each 9–12 people.
Links reach people through a family group chat or individual texts. The
repo is meant to become public later, so it must be clean, self-contained
and free of real names.

**Success:** the organizer can set up an exchange, draw names and drop one
link in the family group chat in a few minutes. Everyone finds out who they're
buying for and what that person wants, and nobody learns anything they
shouldn't.

## 2. Goals, non-goals, anti-goals

**Goals (MVP)**
- Create an exchange and get a secret organizer link.
- Organizer adds and removes names, sets households, the exchange date and the price limit, then draws.
- One shared group link where each person claims their own name, then gets a personal link.
- A personal page showing who you're buying for, that person's wish list, and your own editable wish list.
- Strong, repeated prompts to save links: copy, share, bookmark, add to Home Screen.

**Non-goals (later, not now)**
- Reminders and notifications of any kind.
- A full installable web app (offline support, push notifications). Only "add to Home Screen opens your page" is in scope (§6.5).
- Accounts, email, or SMS sending.
- Multiple organizers, or exchanges that run every year.

**Anti-goals (a failure even if it technically works)**
- A participant can see who drew whom, beyond their own recipient. The organizer panel never shows the draw. The organizer *could* open someone's personal link from the panel. That's accepted: the organizer is trusted (Graeme decided, option 1a), and no "link re-sent" detection is built.
- Links that can be guessed or listed.
- A participant loses access with no way back.
- Clunky on a phone. Nearly every user is on a phone, arriving from a text.
- Real names in commits, test data, screenshots or seed data.

## 3. Roles and links

| Link | Who holds it | What it grants |
|---|---|---|
| Organizer link `/a/<token>` | Organizer only | Manage the exchange. Never shown to participants. |
| Group link `/j/<token>` | Everyone (posted in the group chat) | See the exchange name, date and limit, and claim an unclaimed name. |
| Personal link `/p/<token>` | One participant | See your recipient and their list, and edit your own list. |

- Every token is at least 128 bits of cryptographically secure randomness, URL-safe (e.g. `secrets.token_urlsafe(24)`). Store the tokens as SHA-256 hashes, so a database leak doesn't expose working links. *(Builder's call: hashing the organizer link is required. Hashing participant links conflicts with the organizer re-copying them (§6.3). Either keep participant tokens unhashed, or encrypt them at rest with an app secret. Pick one and document it.)*
- Tokens never appear in logs. Strip or redact the path in access logs for `/a/`, `/p/` and `/j/`.
- Pages send `Referrer-Policy: no-referrer` and `X-Robots-Tag: noindex`. Personal and organizer pages are `Cache-Control: no-store`.

## 4. The flow (order matters; Graeme decided this)

1. **Create.** Front page → "Create a gift exchange" → enter the exchange name → the organizer panel opens. A first-run interstitial says "This is your organizer link. Don't lose it" (see §6.1).
2. **Add names.** The organizer types each person's name. **Nobody is added automatically, the organizer included.** An organizer who wants to take part adds their own name like anyone else.
3. **Households (optional).** The organizer tags people into households. Nobody draws someone in their own household.
4. **Date and price limit.** Set in the panel and shown to everyone. Both are optional, but the panel encourages setting them.
5. **Draw.** Needs at least 3 people. The draw is random and satisfies: nobody draws themselves, nobody draws someone in their own household, and everyone gives exactly once and receives exactly once. If no valid draw exists, show a plain message ("Can't draw: Household A has too many people for this group") and change nothing.
6. **Share the group link.** The group link and its Copy/Share buttons only appear **after** the draw. Before that, the panel says "Draw names first."
7. **Claim.** A person opens the group link, taps their name, and it's claimed. They're taken to the **Save your link** screen (§6.2). Claimed names show "Already claimed" and can't be tapped.
8. **Wish lists.** After claiming, a person can add, edit and remove wish-list items at any time.

### Re-draw after changes (Graeme decided)
Adding or removing a person after the draw requires a re-draw. Before re-drawing, the organizer sees a warning: "Everyone gets a new person. Links and wish lists are kept." Claims and personal links survive the re-draw. Removing a person deletes their wish list.

*(My call: there's an explicit "Re-draw" button. Adding or removing a person after the draw marks the draw out of date. Until the organizer re-draws, participants' pages say "The organizer is updating the draw, check back soon" instead of showing a recipient who may be wrong.)*

## 5. Screens

See the mockups for layout. All screens are designed for phones first and also work on desktop.

1. **Group link, pick your name.** Exchange name, date and limit. "Who are you?" Name buttons; claimed names greyed out with "Already claimed". Footer: "Name taken and it wasn't you? Ask the organizer to reset it."
2. **Save your link.** "Hi <name>. Save your personal link now." The link shown in full, **Copy link** and **Share…** buttons, a list of ways to save it (bookmark it, paste it into a note or text it to yourself, add it to your Home Screen, with steps for that phone), and an "I've saved my link" checkbox that must be ticked before "Continue to my page".
3. **Your page.** A reminder bar ("Haven't saved your link yet?" with Copy and Share…) until saving is confirmed. *(My call: saving is confirmed by ticking the checkbox; store the confirmation server-side on the participant.)* The exchange name, date and limit. "<name>, you're buying for <recipient>" (or "Names haven't been drawn yet" if the draw is out of date). The recipient's wish list. "Your wish list": add an item (text required, link optional) and remove or edit items.
4. **Organizer panel.** A red "This is your organizer link. Don't lose it" box with Copy and Share…, plus the exchange name, date and limit. A people list with household tags and Joined / Not yet; tapping a person offers rename, remove, set household, reset claim, and copy/share their personal link. Add name. Draw / Re-draw. The group link with Copy and Share… (after the draw only).

**The organizer panel never shows who drew whom.**

## 6. Lost links and saving links

### 6.1 Organizer link (Graeme decided: bookmark-and-save is enough)
- No PIN or recovery phrase for now.
- When the exchange is created, a full-screen step: "This is your organizer link. Don't lose it. There's no account; without this link you can't manage the exchange. Never post it in the group chat." It has Copy, Share… and Home Screen steps, plus an "I've saved it" checkbox that must be ticked before continuing.
- The red reminder box stays at the top of the panel permanently, not just until confirmed.

### 6.2 Personal link
- The Save-your-link step comes right after claiming (screen 2).
- A reminder bar on the personal page until confirmed.
- **If it's lost:** the organizer opens the panel, taps the person, and uses Copy/Share for their personal link, then texts it to them.

### 6.2a Sending a personal link directly (my call)
Every person has a personal link as soon as they're added. The organizer can copy or share it to someone who'll never use the group link, such as an older relative. **The first time a personal link is opened, the name counts as claimed**, the same as tapping it in the group link, and the person then goes through the Save-your-link step.

### 6.2b One phone, several names (my call)
Allowed. A parent can claim for kids. Nothing locks a device to one name. Rate limits on claiming are loose enough that a whole family on one home Wi-Fi is never blocked (e.g. 30 claims per IP per 10 minutes).

### 6.3 Wrong claim
A person claimed someone else's name, by mistake or as a joke. The organizer taps that person and picks **Reset claim**. This makes a new personal link for the person (the old link stops working) and marks the name unclaimed, so the real person can claim it from the group link. The wish list is kept.

*(My call: a reset makes a new personal token, so whoever wrongly claimed it loses access.)*

### 6.4 Copy and Share buttons (Graeme decided)
**Every Copy button has a Share… button next to it.** Share uses the Web Share API (`navigator.share`) to open the phone's share menu. If that isn't available (most desktops), the Share button is hidden and Copy remains.

### 6.5 Add to Home Screen
A website can't trigger "Add to Home Screen" directly: on iPhone it's only in Safari's own share menu. So:
- Next to Share, a short tip based on the phone's operating system: "iPhone: tap Safari's Share icon, then Add to Home Screen." and "Android: tap ⋮ in Chrome, then Add to Home screen."
- The home-screen icon must open **that person's own page** (or the organizer panel), not the front page. Ship a web app manifest for each page (or none, so iOS uses the current URL) with `start_url` set to the current personal or organizer URL, plus an app name and icon. *(Builder's call how; verify on iOS Safari and Android Chrome.)*

## 7. Wish lists

- An item = free text (required, max ~300 characters) + optional link (http/https only, max ~2000 characters).
- Links are shown as plain links with `rel="noopener noreferrer nofollow"` and `target="_blank"`.
- Only the person who drew you can see your list (and you, on your own page). The organizer panel doesn't show lists.
- *(My call: no limit on the number of items beyond a sanity cap of ~50 each.)*

## 8. How it's built (my calls, matching Graeme's other apps)

- **Stack:** Python 3.11+, FastAPI, Jinja2 server-rendered pages, a small amount of plain JavaScript (copy, share, phone-specific tips, checkbox gating). No front-end framework or build step.
- **Storage:** SQLite on a mounted Docker volume. It's self-contained, which suits a repo that will be public and easy to self-host. *(Builder may propose the shared Postgres instead if there's a strong reason.)*
- **Data model (sketch):**
  - `exchange` (id, name, date, price_limit, admin_token_hash, join_token, created_at, draw_state: `none|current|stale`)
  - `participant` (id, exchange_id, display_name, household (nullable text), personal_token, claimed_at, link_saved_at)
  - `assignment` (exchange_id, giver_id, receiver_id) — rewritten on every draw
  - `wish_item` (id, participant_id, text, url, position, created_at)
- **Draw algorithm:** random shuffle with retry, under the constraints. Groups are at most ~50, so a simple backtracking search is fine. If it fails, report it rather than loosening the rules.
- **Abuse protection (public site):** per-IP rate limits on creating exchanges and on claiming; caps of 100 participants per exchange and the wish-list caps above; CSRF protection on all state-changing forms (or same-origin checks on POST). Server-side input-length limits.
- **Data retention:** *(My call)* delete an exchange automatically 60 days after its exchange date, or 1 year after it was created if no date was set. Say so on the front page.
- **Privacy:** no analytics, no third-party scripts or fonts in production (self-host any fonts). No real names anywhere in the repo: tests and seed data use made-up names.
- **Repo hygiene:** a README suitable for a public repo, an MIT licence *(my call)*, `.gitignore` for the SQLite file and `.superpowers/`.
- **Observability:** follows `infrastructure/apps/_template`: `/health`, Prometheus `/metrics` via `prometheus-fastapi-instrumentator`, `TZ=America/Toronto`.
- **Tests:** unit tests for the draw (constraints, impossible cases, re-draw keeps links), token handling, and claim/reset; route tests for every flow.

## 9. Deployment

Follows `infrastructure/CLAUDE.md` → "Adding a new app" (own repo):
- `Dockerfile` and a `deploy/` directory in this repo: `deploy/compose.yml` (service block, `build: ..`, SQLite volume, portal and metrics labels) and `deploy/dynamic-gift-exchange.yml` (Traefik route).
- **Public access:** apps.graemecrawley.com needs no login (Graeme confirmed), so the app is public as soon as it is routed. No Cloudflare Access change is needed.
- Hostname (Graeme decided): on `apps.graemecrawley.com`. *(My call: path prefix `apps.graemecrawley.com/gift-exchange`, Traefik strips the prefix; the app must work under a path prefix, i.e. respect `root_path`.)*
- Because of the Friday deadline, ask infrastructure to onboard as soon as a first working version exists, not at the very end.
- *(My call)* `deploy/` stays in this repo for now, following the infrastructure convention. Before the repo goes public, the hostname moves out of `deploy/` (environment variable or a private overlay), because it contains a personal name.
- This session does **not** run docker on live containers. When it's ready, ask the infrastructure session to onboard and deploy it.

## 10. Deadline and what gets cut first

Live by Friday 2026-11-06. Must ship: §4 flow, §5 screens, §6.1–6.4, §7, token security (§3), the draw with households, and basic rate limits. Cut first if short of time, in this order (my call): automatic data deletion (§8, add a manual note instead), per-page Home Screen manifest polish (§6.5; keep the text tips), editing a wish-list item in place (delete and re-add instead). A UI specialist session is available for visual polish on the screens (Graeme's offer).

## 11. Left to the builder

- Visual polish beyond the mockups: keep it calm and readable; warm, not kitschy.
- How phone type is detected for the Home Screen tips.
- Exact rate-limit numbers.
- Whether participant tokens are stored unhashed or encrypted (§3).
