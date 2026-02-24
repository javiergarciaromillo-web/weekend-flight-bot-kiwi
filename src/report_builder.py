from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from typing import Iterable
from dateutil import parser


@dataclass(frozen=True)
class FlightLine:
    price: float
    currency: str
    carrier_code: str | None
    flight_no: str | None
    out_time: str
    in_time: str


def _isoparse(s: str | None) -> datetime | None:
    if not s:
        return None
    try:
        return parser.isoparse(s)
    except Exception:
        return None


def _first_segment(leg: dict) -> dict | None:
    segs = (leg or {}).get("sectorSegments") or []
    if not segs:
        return None
    return (segs[0] or {}).get("segment") or None


def _last_segment(leg: dict) -> dict | None:
    segs = (leg or {}).get("sectorSegments") or []
    if not segs:
        return None
    return (segs[-1] or {}).get("segment") or None


def _leg_dep_local(leg: dict) -> datetime | None:
    seg = _first_segment(leg)
    if not seg:
        return None
    return _isoparse(((seg.get("source") or {}).get("localTime")))


def _leg_arr_local(leg: dict) -> datetime | None:
    seg = _last_segment(leg)
    if not seg:
        return None
    return _isoparse(((seg.get("destination") or {}).get("localTime")))


def _leg_carrier_and_flight(leg: dict) -> tuple[str | None, str | None]:
    seg = _first_segment(leg) or {}
    carrier = seg.get("carrier") or {}
    ccode = carrier.get("code")
    fcode = seg.get("code")
    flight_no = f"{ccode}{fcode}" if ccode and fcode else None
    return ccode, flight_no


def _pattern_from_weekdays(out_dep: datetime, in_dep: datetime) -> str | None:
    # Mon=0 ... Sun=6
    out_w = out_dep.weekday()
    in_w = in_dep.weekday()

    if out_w == 4 and in_w == 6:
        return "Fri → Sun"
    if out_w == 3 and in_w == 6:
        return "Thu → Sun"
    if out_w == 4 and in_w == 0:
        return "Fri → Mon"
    if out_w == 3 and in_w == 0:
        return "Thu → Mon"
    return None


def _weekend_start_thu(out_dep: datetime) -> date:
    return (out_dep.date() - timedelta(days=1)) if out_dep.weekday() == 4 else out_dep.date()


def _within_next_weeks(d: date, weeks: int) -> bool:
    today = date.today()
    return today <= d <= (today + timedelta(days=7 * weeks))


def collect_weekend_report(
    itineraries: Iterable[dict],
    currency: str,
    weeks: int,
    min_out_time: time,
    min_in_time: time,
) -> dict[date, dict[str, list[FlightLine]]]:
    """
    weekend_start_date -> pattern_label -> top3 FlightLine sorted by price
    Filters:
      - pattern must be one of Thu/Fri -> Sun/Mon combos
      - out_dep >= min_out_time
      - in_dep  >= min_in_time
      - weekend_start within next `weeks` weeks
    """
    buckets: dict[date, dict[str, list[FlightLine]]] = {}

    for it in itineraries:
        amount_s = (it.get("price") or {}).get("amount")
        if not amount_s:
            continue
        try:
            price = float(amount_s)
        except ValueError:
            continue

        out_leg = it.get("outbound") or {}
        in_leg = it.get("inbound") or {}

        out_dep = _leg_dep_local(out_leg)
        in_dep = _leg_dep_local(in_leg)
        if out_dep is None or in_dep is None:
            continue

        pattern = _pattern_from_weekdays(out_dep, in_dep)
        if pattern is None:
            continue

        if out_dep.time() < min_out_time:
            continue
        if in_dep.time() < min_in_time:
            continue

        wstart = _weekend_start_thu(out_dep)
        if not _within_next_weeks(wstart, weeks=weeks):
            continue

        out_arr = _leg_arr_local(out_leg)
        in_arr = _leg_arr_local(in_leg)

        ccode, flight_no = _leg_carrier_and_flight(out_leg)
        out_time = f"{out_dep.strftime('%H:%M')}—{(out_arr or out_dep).strftime('%H:%M')}"
        in_time = f"{in_dep.strftime('%H:%M')}—{(in_arr or in_dep).strftime('%H:%M')}"

        line = FlightLine(
            price=price,
            currency=currency,
            carrier_code=ccode,
            flight_no=flight_no,
            out_time=out_time,
            in_time=in_time,
        )

        buckets.setdefault(wstart, {}).setdefault(pattern, []).append(line)

    for ws, patterns in buckets.items():
        for p, lines in patterns.items():
            lines.sort(key=lambda x: x.price)
            patterns[p] = lines[:3]

    return buckets
