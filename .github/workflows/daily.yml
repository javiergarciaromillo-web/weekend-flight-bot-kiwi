from __future__ import annotations

import os
from dataclasses import dataclass
from zoneinfo import ZoneInfo


@dataclass(frozen=True)
class Config:
    rapidapi_key: str
    rapidapi_host: str
    base_url: str

    smtp_host: str
    smtp_port: int
    smtp_user: str
    smtp_pass: str
    email_to: str

    origins: tuple[str, ...]
    destination: str
    weeks: int
    top_n: int
    direct_stops: int

    # separate time windows
    out_time_from: str
    out_time_to: str
    in_time_from: str
    in_time_to: str

    # how to apply time window: DEPART | ARRIVE | EITHER
    out_time_mode: str
    in_time_mode: str

    timezone: ZoneInfo
    refresh_every_days: int
    subject_base: str


def _req(name: str) -> str:
    v = os.getenv(name, "").strip()
    if not v:
        raise RuntimeError(f"Missing required env var: {name}")
    return v


def _mode(name: str, default: str) -> str:
    v = os.getenv(name, default).strip().upper()
    if v not in {"DEPART", "ARRIVE", "EITHER"}:
        raise RuntimeError(f"{name} must be one of DEPART|ARRIVE|EITHER, got: {v}")
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

    out_time_from = os.getenv("OUT_TIME_FROM", "16:00").strip()
    out_time_to = os.getenv("OUT_TIME_TO", "23:00").strip()

    in_time_from = os.getenv("IN_TIME_FROM", "16:00").strip()
    in_time_to = os.getenv("IN_TIME_TO", "23:00").strip()

    # Defaults chosen to match your concern:
    # - outbound: departure window
    # - inbound: arrival window (so 15:35-18:05 counts because arrival 18:05)
    out_time_mode = _mode("OUT_TIME_MODE", "DEPART")
    in_time_mode = _mode("IN_TIME_MODE", "ARRIVE")

    tz = ZoneInfo(os.getenv("TZ", "Europe/Madrid").strip())
    refresh_every_days = int(os.getenv("REFRESH_EVERY_DAYS", "6"))
    subject_base = os.getenv("EMAIL_SUBJECT", "AMS/RTM - BCN").strip()

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
        out_time_from=out_time_from,
        out_time_to=out_time_to,
        in_time_from=in_time_from,
        in_time_to=in_time_to,
        out_time_mode=out_time_mode,
        in_time_mode=in_time_mode,
        timezone=tz,
        refresh_every_days=refresh_every_days,
        subject_base=subject_base,
    )
