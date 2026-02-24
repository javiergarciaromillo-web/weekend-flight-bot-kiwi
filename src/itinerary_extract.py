import re
from datetime import datetime, time
from dateutil import parser


ISO_LIKE = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}")


def _walk(obj):
    """Yield all (path, value) pairs in a nested dict/list structure."""
    stack = [("", obj)]
    while stack:
        path, cur = stack.pop()
        if isinstance(cur, dict):
            for k, v in cur.items():
                p = f"{path}.{k}" if path else str(k)
                stack.append((p, v))
        elif isinstance(cur, list):
            for i, v in enumerate(cur):
                p = f"{path}[{i}]"
                stack.append((p, v))
        else:
            yield path, cur


def _find_iso_datetimes(obj):
    """Return list of datetimes parsed from ISO-like strings found in obj."""
    out = []
    for _path, v in _walk(obj):
        if isinstance(v, str) and ISO_LIKE.search(v):
            try:
                out.append(parser.isoparse(v))
            except Exception:
                pass
    return out


def _find_flight_tokens(obj):
    """
    Collect candidate flight numbers and carrier codes from common key patterns.
    Returns (carriers, flight_numbers) as comma-separated strings (may be '').
    """
    carriers = set()
    flight_numbers = set()

    for path, v in _walk(obj):
        if not isinstance(v, (str, int)):
            continue

        key = path.split(".")[-1]

        # carrier codes often appear under keys like 'carrier', 'airline', 'marketingCarrier'
        if isinstance(v, str) and key.lower() in {"carrier", "airline", "carrierCode".lower(), "airlineCode".lower()}:
            if 2 <= len(v) <= 4 and v.isalnum():
                carriers.add(v)

        # flight number often as int or string under keys like 'flightNumber'
        if key.lower() in {"flightnumber", "flight_number", "flightno", "flight"}:
            s = str(v).strip()
            if 1 <= len(s) <= 6 and s.replace("-", "").isalnum():
                flight_numbers.add(s)

        # sometimes nested objects: carrier: {code: "VY"}
        if key.lower() == "code" and isinstance(v, str):
            # only accept short-ish codes to avoid grabbing random IDs
            if 2 <= len(v) <= 3 and v.isalnum():
                carriers.add(v)

    return ", ".join(sorted(carriers)), ", ".join(sorted(flight_numbers))


def extract_leg_departure_local(leg_obj) -> datetime | None:
    """
    Best-effort: find a local departure datetime in the leg object.
    Strategy:
      - parse all ISO-like datetimes found inside leg
      - pick the earliest as 'departure' (usually first segment takeoff)
    """
    dts = _find_iso_datetimes(leg_obj)
    if not dts:
        return None
    return min(dts)


def leg_ok_after(leg_obj, min_time: time) -> tuple[bool, datetime | None]:
    dep = extract_leg_departure_local(leg_obj)
    if dep is None:
        return False, None
    return dep.time() >= min_time, dep


def extract_itinerary_summary(itinerary: dict) -> dict:
    """
    Returns a summary dict with:
      - out_dep (datetime|None)
      - in_dep (datetime|None)
      - carriers (string)
      - flight_numbers (string)
    """
    outbound = itinerary.get("outbound", {})
    inbound = itinerary.get("inbound", {})

    out_dep = extract_leg_departure_local(outbound)
    in_dep = extract_leg_departure_local(inbound)

    carriers_out, flights_out = _find_flight_tokens(outbound)
    carriers_in, flights_in = _find_flight_tokens(inbound)

    carriers = ", ".join([x for x in [carriers_out, carriers_in] if x]).strip(", ")
    flight_numbers = ", ".join([x for x in [flights_out, flights_in] if x]).strip(", ")

    return {
        "out_dep": out_dep,
        "in_dep": in_dep,
        "carriers": carriers,
        "flight_numbers": flight_numbers,
    }
