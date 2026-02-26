from __future__ import annotations

import os
from dataclasses import dataclass
from zoneinfo import ZoneInfo


@dataclass(frozen=True)
class Config:
    # RapidAPI
    rapidapi_key: str
    rapidapi_host: str
    base_url: str

    # Mail (SMTP)
    smtp_host: str
    smtp_port: int
    smtp_user: str
    smtp_pass: str
    email_to: str

    # Search scope
    origins: tuple[str, ...]
    destination: str
    weeks: int
    top_n: int
    direct_stops: int

    # Time window (local time at airports)
    time_from: str  # "HH:MM"
    time_to: str    # "HH:MM"
    timezone: ZoneInfo

    # Refresh policy
    refresh_every_days: int

    # Email subject
    subject: str


def _req(name: str) -> str:
    v = os.getenv(name, "").strip()
    if not v:
        raise RuntimeError(f"Missing required env var: {name}")
    return v


def load_config() -> Config:
    rapidapi_key = _req("RAPIDAPI_KEY")
    rapidapi_host = os.getenv("RAPIDAPI_HOST", "flights-scraper-real-time.p.rapidapi.com").strip()
    base_url = os.getenv("BASE_URL", "https://flights-scraper-real-time.p.rapidapi.com").strip()

    smtp_host = _req("SMTP_HOST")
    smtp_port = int(_req("SMTP_PORT"))
    smtp_user = _req("SMTP_USER")
    smtp_pass = _req("SMTP_PASS")
    email_to = _req("EMAIL_TO")

    origins = tuple(os.getenv("ORIGINS", "AMS,RTM").replace(" ", "").split(","))
    destination = os.getenv("DESTINATION", "BCN").strip()

    weeks = int(os.getenv("WEEKS", "3"))
    top_n = int(os.getenv("TOP_N", "3"))
    direct_stops = int(os.getenv("STOPS", "0"))

    time_from = os.getenv("TIME_FROM", "16:00").strip()
    time_to = os.getenv("TIME_TO", "23:00").strip()

    tz = ZoneInfo(os.getenv("TZ", "Europe/Madrid").strip())

    refresh_every_days = int(os.getenv("REFRESH_EVERY_DAYS", "6"))

    subject = os.getenv("EMAIL_SUBJECT", "AMS/RTM - BCN").strip()

    return Config(
        rapidapi_key=rapidapi_key,
        rapidapi_host=rapidapi_host,
        base_url=base_url,
        smtp_host=smtp_host,
        smtp_port=smtp_port,
        smtp_user=smtp_user,
        smtp_pass=smtp_pass,
        email_to=email_to,
        origins=origins,
        destination=destination,
        weeks=weeks,
        top_n=top_n,
        direct_stops=direct_stops,
        time_from=time_from,
        time_to=time_to,
        timezone=tz,
        refresh_every_days=refresh_every_days,
        subject=subject,
    )
