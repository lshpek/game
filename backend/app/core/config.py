"""Application configuration loaded from environment variables.

All tunables live here so that no business logic hard-codes environment
values, secrets or magic numbers.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Annotated, Any, Literal

from pydantic import field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parents[2]
PROJECT_ROOT = BACKEND_DIR.parent

# ``NoDecode`` keeps pydantic-settings from JSON-parsing these fields, so the
# ``_split_csv`` validator receives the raw environment string instead.
CsvList = Annotated[list[str], NoDecode]
CsvIntList = Annotated[list[int], NoDecode]


class Settings(BaseSettings):
    """Runtime settings for the API, bot and CLI entry points."""

    model_config = SettingsConfigDict(
        env_file=(PROJECT_ROOT / ".env", BACKEND_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # --- Application ---------------------------------------------------
    app_env: Literal["development", "test", "production"] = "development"
    debug: bool = True
    app_name: str = "NUMORA — Global collectible numbers"
    api_prefix: str = "/api"
    secret_key: str = "CHANGE_ME_TO_RANDOM_SECRET"
    jwt_algorithm: str = "HS256"
    access_token_ttl_seconds: int = 60 * 60 * 24 * 7
    log_level: str = "INFO"

    # --- Database ------------------------------------------------------
    database_url: str = "sqlite:///./app.db"
    db_echo: bool = False
    db_pool_size: int = 5
    db_max_overflow: int = 10

    # --- Telegram ------------------------------------------------------
    bot_token: str = "CHANGE_ME"
    telegram_bot_username: str = "CHANGE_ME"
    telegram_webhook_url: str = ""
    telegram_init_data_ttl_seconds: int = 60 * 60 * 24
    telegram_payment_provider_token: str = "CHANGE_ME"
    telegram_webhook_secret: str = "CHANGE_ME"
    service_token: str = "CHANGE_ME"

    # --- URLs ----------------------------------------------------------
    frontend_url: str = "http://localhost:5173"
    backend_url: str = "http://localhost:8000"
    cors_origins: CsvList = ["http://localhost:5173"]
    mini_app_short_name: str = "numora"

    # --- Access control ------------------------------------------------
    admin_telegram_ids: CsvIntList = []
    allow_dev_login: bool = True

    # --- Economy tuning --------------------------------------------------
    default_daily_rolls: int = 10
    premium_daily_rolls: int = 25
    daily_streak_bonus_coins: int = 25
    daily_base_coins: int = 0
    roll_coin_reward_chance: float = 0.35
    roll_coin_reward_min: int = 1
    roll_coin_reward_max: int = 15

    # --- Referrals ------------------------------------------------------
    referral_reward_coins: int = 250
    referral_reward_rolls: int = 3
    max_referrals_per_day: int = 20

    # --- Rate limiting (requests per window, window in seconds) ---------
    rate_limit_enabled: bool = True
    rate_limit_default: int = 120
    rate_limit_window_seconds: int = 60
    rate_limit_roll: int = 30
    # Auth is unauthenticated and therefore keyed by IP: strict enough to stop
    # credential stuffing, tolerant of shared/carrier NAT addresses.
    rate_limit_auth: int = 60
    rate_limit_referral: int = 10
    rate_limit_payment: int = 10
    rate_limit_admin: int = 60
    # Internal control surfaces (Telegram admin panel) get their own bucket so a
    # burst of panel taps can never exhaust the interactive admin API quota.
    rate_limit_admin_bot: int = 120
    rate_limit_admin_read: int = 240

    # --- Payments -------------------------------------------------------
    payment_provider: Literal["telegram_stars", "mock"] = "mock"
    payment_currency: str = "XTR"

    # Optional JSON override for the rarity weight table, e.g.
    # RARITY_WEIGHTS_OVERRIDE={"COMMON": 70, "UNCOMMON": 20, ...}
    rarity_weights_override: str | None = None

    # --- Frontend build -------------------------------------------------
    vite_api_base_url: str = "http://localhost:8000"

    # --- Bootstrapping ---------------------------------------------------
    auto_migrate: bool = True
    auto_seed: bool = True

    @property
    def rarity_weights(self) -> dict[str, float]:
        """Effective rarity weights (defaults, optionally overridden by env)."""
        from app.game.rarity import load_rarity_weights

        return load_rarity_weights(self.rarity_weights_override)

    @field_validator("cors_origins", "admin_telegram_ids", mode="before")
    @classmethod
    def _split_csv(cls, value: Any) -> Any:
        """Allow comma-separated env values for list settings."""
        if value is None or value == "":
            return []
        if isinstance(value, str):
            return [item.strip() for item in value.split(",") if item.strip()]
        return value

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"

    @property
    def is_sqlite(self) -> bool:
        return self.database_url.startswith("sqlite")

    def telegram_mini_app_link(self, start_param: str | None = None) -> str:
        base = f"https://t.me/{self.telegram_bot_username}/{self.mini_app_short_name}"
        if start_param:
            return f"{base}?startapp={start_param}"
        return base


@lru_cache
def get_settings() -> Settings:
    """Cached settings accessor (import-time safe)."""
    return Settings()


settings = get_settings()
