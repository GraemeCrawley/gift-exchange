# /// script
# dependencies = ["pillow"]
# ///
"""Make the Home Screen icons: one per colour, for organizers and for everyone else.

Run from the repo root:  uv run scripts/make_icons.py
"""

import sys
from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from app.themes import ICON_SIZES, THEMES  # noqa: E402

OUT = ROOT / "app" / "static" / "icons"
PAPER = "#F7F4EE"
S = 4  # draw big, shrink down, for smooth edges


def star(cx, cy, r_out, r_in):
    # cy is the star's middle; callers nudge it down so the gaps above and below look even.
    import math

    pts = []
    for i in range(10):
        r = r_out if i % 2 == 0 else r_in
        a = math.pi / 2 + i * math.pi / 5
        pts.append((cx + r * math.cos(a), cy - r * math.sin(a)))
    return pts


def draw(color: dict, organizer: bool) -> Image.Image:
    n = 512 * S
    img = Image.new("RGB", (n, n), color["primary"])
    d = ImageDraw.Draw(img)
    k = lambda *v: [x * S for x in v]  # noqa: E731
    ribbon = color["ribbon"]
    d.ellipse(k(150, 81, 260, 145), fill=ribbon)  # bow
    d.ellipse(k(254, 81, 364, 145), fill=ribbon)
    d.rectangle(k(188, 103, 222, 124), fill=color["primary"])
    d.rectangle(k(290, 103, 325, 124), fill=color["primary"])
    d.rectangle(k(82, 144, 431, 205), fill=PAPER)  # lid
    d.rectangle(k(103, 205, 410, 420), fill=PAPER)  # box
    d.rectangle(k(236, 158, 277, 420), fill=ribbon)  # ribbon
    if organizer:  # a star badge so the organizer's icon stands out
        cx, cy, r = 386, 386, 84  # kept clear of the corner iPhone rounds off
        d.ellipse(k(cx - r - 12, cy - r - 12, cx + r + 12, cy + r + 12), fill=color["primary"])
        d.ellipse(k(cx - r, cy - r, cx + r, cy + r), fill="#FFFFFF")
        d.polygon([(x * S, y * S) for x, y in star(cx, cy + 7, 60, 25)], fill="#E0A21B")
    return img


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    for key, color in THEMES.items():
        for role in ("member", "organizer"):
            big = draw(color, role == "organizer")
            for size in ICON_SIZES:
                big.resize((size, size), Image.LANCZOS).save(OUT / f"{key}-{role}-{size}.png", optimize=True)
    print(f"wrote {len(THEMES) * 2 * len(ICON_SIZES)} icons to {OUT}")


if __name__ == "__main__":
    main()
