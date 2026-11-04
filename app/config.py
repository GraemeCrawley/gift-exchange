import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    db_path: str
    root_path: str
    public_base_url: str


def load_settings() -> Settings:
    return Settings(
        db_path=os.environ.get("GIFT_DB_PATH", "./data/gift.db"),
        root_path=os.environ.get("ROOT_PATH", "").rstrip("/"),
        public_base_url=os.environ.get("PUBLIC_BASE_URL", "").rstrip("/"),
    )
