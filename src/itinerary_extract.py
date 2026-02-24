from __future__ import annotations

from datetime import datetime, time
from dateutil import parser


def _parse_local_time(s: str | None) -> datetime | None:
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
    return (segs[0] or {}).get("segment")


def extract_leg_departure_local(leg: dict) -> datetime | None:
    seg = _first_segment(leg)
    if not seg:
        return None
    return _parse_local_time(((seg.get("source") or {}).get("localTime")))


def extract_leg_flights(leg: dict) -> tuple[str | None, str | None]:
    """
    Returns:
      carriers: e.g. "HV(Transavia)" or "HV(Transavia), VY(Vueling)"
      flights: e.g. "HV5131, HV5136"
    """
    segs = (leg or {}).get("sectorSegments") or []
    carriers = []
    flights = []

    for ss in segs:
        seg = (ss or {}).get("segment") or {}
        carrier = seg.get("carrier") or {}
        ccode = carrier.get("code")
        cname = carrier.get("name")
        fcode = seg.get("code")  # flight number part like "5131"

        if ccode and cname:
            carriers.append(f"{ccode}({cname})")
        elif ccode:
            carriers.append(str(ccode))

        if ccode and fcode:
            flights.append(f"{ccode}{fcode}")
        elif fcode:
            flights.append(str(fcode))

    carriers_str = ", ".join(carriers) if carriers else None
    flights_str = ", ".join(flights) if flights else None
    return carriers_str, flights_str


def itinerary_ok_after(itinerary: dict, min_time: time) -> tuple[bool, datetime | None, datetime | None]:
    outbound = itinerary.get("outbound") or {}
    inbound = itinerary.get("inbound") or {}

    out_dep = extract_leg_departure_local(outbound)
    in_dep = extract_leg_departure_local(inbound)

    if out_dep is None or in_dep is None:
        return False, out_dep, in_dep

    return (out_dep.time() >= min_time) and (in_dep.time() >= min_time), out_dep, in_dep
