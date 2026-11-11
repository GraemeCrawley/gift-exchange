"""Colours an organizer can pick for an exchange.

primary / primary_dark are the light-mode accent; night / night_dark the dark-mode one.
ribbon colours the gift's ribbon and bow on the Home Screen icon.
Icons are pre-made PNGs (iPhone needs a real image file): run scripts/make_icons.py after editing.
"""

THEMES = {
    "green": {"label": "Green", "primary": "#2F6B4F", "primary_dark": "#1F4A36", "night": "#6FBF97", "night_dark": "#8FD3B0", "ribbon": "#A23B2A"},
    "red": {"label": "Red", "primary": "#A6322B", "primary_dark": "#7A211B", "night": "#E8877E", "night_dark": "#F2AAA3", "ribbon": "#2F6B4F"},
    "blue": {"label": "Blue", "primary": "#2D5F9A", "primary_dark": "#1E4170", "night": "#7FB0E6", "night_dark": "#A6C9F0", "ribbon": "#A23B2A"},
    "purple": {"label": "Purple", "primary": "#6B3F8F", "primary_dark": "#4C2B67", "night": "#B693D6", "night_dark": "#CDB3E6", "ribbon": "#A23B2A"},
    "gold": {"label": "Gold", "primary": "#8A6414", "primary_dark": "#634708", "night": "#E0B65A", "night_dark": "#ECCD86", "ribbon": "#A23B2A"},
    "charcoal": {"label": "Charcoal", "primary": "#3D4349", "primary_dark": "#262B30", "night": "#AEB6BE", "night_dark": "#CBD1D7", "ribbon": "#A23B2A"},
}
DEFAULT = "green"
ICON_SIZES = (180, 192, 512)


def theme(color: str | None) -> dict:
    return THEMES.get(color or DEFAULT, THEMES[DEFAULT])


def icon_path(color: str | None, role: str, size: int) -> str:
    """Static path of the Home Screen icon. role is 'organizer' or 'member'."""
    color = color if color in THEMES else DEFAULT
    return f"/static/icons/{color}-{role}-{size}.png"
