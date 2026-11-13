## 2026-11-03
**Worked on:** New gift-exchange app: brainstormed design with Graeme, wrote spec + plan, built MVP on branch `mvp` (create, names, households, draw, group-link claim, save-your-link, wish lists, copy/share, manifest, rate limits). Live at apps.graemecrawley.com/gift-exchange via infrastructure.
**Decisions:** No accounts; tokens in URLs. Organizer trusted (can open personal links). Group link appears only after draw. Re-draw keeps links. SQLite on volume. Prefix /gift-exchange.
**Gotchas:** Passing the prefix to FastAPI root_path made /static 404 behind Traefik strip — keep prefix in app.state only. Restart local uvicorn after adding Jinja filters. `pkill -f` with a pattern in the same shell command kills the shell itself.
**Next:** Final review fixes; real-phone check of Share + Add to Home Screen on live; merge mvp → main.

## 2026-11-04
**Worked on:** Phone-test fixes: stay on add box after adding a name, iPhone date box, cache-busting CSS/JS, Households page (drag/tap), simpler save-link copy, "Are you X?" claim confirm, countdown + limit tiles, dark-mode reminder button.
**Decisions:** Household labels derived from member names; stored value is an opaque group key. Claim is now GET confirm page + POST.
**Gotchas:** Chrome skips autofocus when URL has a #fragment, and the fragment jump clears focus — focus in JS after load. Restart local uvicorn after adding Jinja filters.
**Next:** Infra rebuild of 5225a6d; Graeme phone test (does Share… sheet offer Add to Home Screen on iPhone?); merge mvp → main.

## 2026-11-13
**Worked on:** Re-draw resets claims; per-exchange colour (picked at creation too) with organizer star icon; shorter "Save this page" (Home Screen steps first, copy as backup, no Share… button). Repo public on GitHub.
**Decisions:** Icons are pre-made PNGs per colour/role (scripts/make_icons.py). Colour chosen on the create form because iPhone never updates an added icon.
**Gotchas:** Black icons on iPhone = iOS Dark icon style (Edit → Customize → Light). `uv run --with` in repo root creates uv.lock; use --no-project.
**Next:** Push 56232d2 + 1dda893 to GitHub if Graeme says so; fit in the designer's new icon if one arrives.
