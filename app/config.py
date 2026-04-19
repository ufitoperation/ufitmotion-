import os
from dataclasses import dataclass


@dataclass
class Config:
    SECRET_KEY: str
    DATABASE_URL: str | None
    DB_PATH: str
    APP_ENV: str
    APP_BASE_URL: str


def get_config() -> Config:
    env = os.environ.get("APP_ENV", "development")
    secret_key = os.environ.get("UFIT_SECRET_KEY", "")
    if not secret_key and env == "production":
        raise RuntimeError("UFIT_SECRET_KEY must be set in production")
    if not secret_key:
        secret_key = "dev-insecure-key-change-me"
    return Config(
        SECRET_KEY=secret_key,
        DATABASE_URL=os.environ.get("DATABASE_URL"),
        DB_PATH=os.environ.get("DB_PATH", "ufit_motion.db"),
        APP_ENV=env,
        APP_BASE_URL=os.environ.get("UFIT_APP_BASE_URL", "http://localhost:5000"),
    )
