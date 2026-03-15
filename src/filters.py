from __future__ import annotations

from datetime import datetime, time
from src.models import FlightOption, SearchConfig


def _parse_hhmm(value: str) -> time:
    return datetime.strptime(value, "%H:%M").time()


def filter_options(options: list[FlightOption], cfg: SearchConfig) -> list[FlightOption]:
    allowed = {a.strip().lower() for a in cfg.allowed_airlines}
    min_time = cfg.min_departure_time

    filtered: list[FlightOption] = []
    for option in options:
        airline_ok = option.airline.strip().lower() in allowed
        departure_ok = _parse_hhmm(option.outbound_departure) >= min_time

        if not airline_ok:
            continue
        if not departure_ok:
            continue

        filtered.append(option)

    return filtered
