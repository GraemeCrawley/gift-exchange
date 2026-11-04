## 2026-11-03
**Worked on:** New gift-exchange app: brainstormed design with Graeme, wrote spec + plan, built MVP on branch `mvp` (create, names, households, draw, group-link claim, save-your-link, wish lists, copy/share, manifest, rate limits). Live at apps.graemecrawley.com/gift-exchange via infrastructure.
**Decisions:** No accounts; tokens in URLs. Organizer trusted (can open personal links). Group link appears only after draw. Re-draw keeps links. SQLite on volume. Prefix /gift-exchange.
**Gotchas:** Passing the prefix to FastAPI root_path made /static 404 behind Traefik strip — keep prefix in app.state only. Restart local uvicorn after adding Jinja filters. `pkill -f` with a pattern in the same shell command kills the shell itself.
**Next:** Final review fixes; real-phone check of Share + Add to Home Screen on live; merge mvp → main.
