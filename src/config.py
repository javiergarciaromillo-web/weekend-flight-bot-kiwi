from __future__ import annotations

import os
import re
from dataclasses import dataclass
from zoneinfo import ZoneInfo


def _req(name: str) -> str:
    v = os.getenv(name, "").strip()
    if not v:
        raise RuntimeError(f"Missing required env var: {name}")
    return v


def _norm_flight_code(s: str) -> str:
    t = re.sub(r"[^A-Za-z0-9]", "", (s or "").upper())
    m = re.match(r"^([A-Z]{2}\d+)", t)
    return m.group(1) if m else t


@dataclass(frozen=True)
class WatchItem:
    weekday: str  # THU/FRI/SUN/MON
    origin: str
    destination: str
    flight_code: str  # e.g. VY8313
    provider: str  # "VUELING" or "TRANSAVIA"


@dataclass(frozen=True)
class Config:
    smtp_host: str
    smtp_port: int
    smtp_user: str
    smtp_pass: str
    email_to: str

    subject_base: str
    tz: ZoneInfo
    time_from: str
    time_to: str
    weeks: int

    watchlist: tuple[WatchItem, ...]


def load_config() -> Config:
    smtp_host = _req("SMTP_HOST")
    smtp_port = int(_req("SMTP_PORT"))
    smtp_user = _req("SMTP_USER")
    smtp_pass = _req("SMTP_PASS")
    email_to = _req("EMAIL_TO")

    subject_base = os.getenv("EMAIL_SUBJECT", "AMS/RTM - BCN").strip()
    tz = ZoneInfo(os.getenv("TZ", "Europe/Madrid").strip())
    time_from = os.getenv("TIME_FROM", "16:00").strip()
    time_to = os.getenv("TIME_TO", "23:00").strip()
    weeks = int(os.getenv("WEEKS", "3").strip())

    wl = (
        # Thursday AMS->BCN (Vueling)
        WatchItem("THU", "AMS", "BCN", _norm_flight_code("VY8313"), "VUELING"),
        WatchItem("THU", "AMS", "BCN", _norm_flight_code("VY8310"), "VUELING"),
        # Friday RTM->BCN (Transavia)
        WatchItem("FRI", "RTM", "BCN", _norm_flight_code("HV6061"), "TRANSAVIA"),
        # Friday AMS->BCN (Vueling)
        WatchItem("FRI", "AMS", "BCN", _norm_flight_code("VY8307"), "VUELING"),
        WatchItem("FRI", "AMS", "BCN", _norm_flight_code("VY8313"), "VUELING"),
        # Sunday BCN->AMS (Vueling + Transavia)
        WatchItem("SUN", "BCN", "AMS", _norm_flight_code("VY8311"), "VUELING"),
        WatchItem("SUN", "BCN", "AMS", _norm_flight_code("VY8312"), "VUELING"),
        WatchItem("SUN", "BCN", "AMS", _norm_flight_code("HV5134"), "TRANSAVIA"),
        # Monday BCN->AMS (Vueling + Transavia)
        WatchItem("MON", "BCN", "AMS", _norm_flight_code("VY8306"), "VUELING"),
        WatchItem("MON", "BCN", "AMS", _norm_flight_code("HV5134"), "TRANSAVIA"),
    )

    return Config(
        smtp_host=smtp_host,
        smtp_port=smtp_port,
        smtp_user=smtp_user,
        smtp_pass=smtp_pass,
        email_to=email_to,
        subject_base=subject_base,
        tz=tz,
        time_from=time_from,
        time_to=time_to,
        weeks=weeks,
        watchlist=wl,
    )
