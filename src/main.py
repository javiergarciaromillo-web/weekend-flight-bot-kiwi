from __future__ import annotations

from collections import defaultdict
from datetime import time, timedelta

from src.kiwi_fetch import fetch_round_trip_by_dates
from src.planner import Pattern, generate_date_pairs
from src.report_builder import collect_weekend_report
from src.email_report import build_html_report, send_email


ORIGINS = {
    "AMS": "City:amsterdam_nl",
    "RTM": "City:rotterdam_nl",
}

DESTINATION = "City:barcelona_es"
CURRENCY = "EUR"
HORIZON_WEEKS = 5
LIMIT_PER_QUERY = 250

MIN_OUT_TIME = time(17, 0)
MIN_IN_TIME = time(17, 0)

PATTERNS = [
    Pattern(name="thu_sun", depart_dow=3, return_dow=6),
    Pattern(name="thu_mon", depart_dow=3, return_dow=0),
    Pattern(name="fri_sun", depart_dow=4, return_dow=6),
    Pattern(name="fri_mon", depart_dow=4, return_dow=0),
]


def _weekend_anchor_thursday(dep):
    # dep is date
    if dep.weekday() == 3:  # Thu
        return dep
    if dep.weekday() == 4:  # Fri
        return dep - timedelta(days=1)
    # fallback
    delta = (dep.weekday() - 3) % 7
    return dep - timedelta(days=delta)


def _first_seg_time(itinerary: dict, leg_key: str) -> str | None:
    leg = itinerary.get(leg_key) or {}
    segs = leg.get("sectorSegments") or []
    if not segs:
        return None
    seg = (segs[0] or {}).get("segment") or {}
    return ((seg.get("source") or {}).get("localTime"))


def main():
    pairs = generate_date_pairs(HORIZON_WEEKS, PATTERNS)

    weekend_origin_itins = defaultdict(lambda: defaultdict(list))

    printed_debug = False

    for pname, dep, ret in pairs:
        anchor = _weekend_anchor_thursday(dep)

        for origin_label, origin in ORIGINS.items():
            data = fetch_round_trip_by_dates(
                source=origin,
                destination=DESTINATION,
                departure_date=dep,
                return_date=ret,
                currency=CURRENCY,
                limit=LIMIT_PER_QUERY,
            )
            itins = data.get("itineraries", []) or []
            weekend_origin_itins[anchor][origin_label].extend(itins)

            # Print debug ONCE (first non-empty response)
            if (not printed_debug) and itins:
                first = itins[0]
                out_time = _first_seg_time(first, "outbound")
                in_time = _first_seg_time(first, "inbound")
                print("REQUESTED:", dep.isoformat(), "→", ret.isoformat(), "| origin", origin_label)
                print("RETURNED :", out_time, "→", in_time)
                print("-" * 60)
                printed_debug = True

    all_origins_buckets = {k: {} for k in ORIGINS.keys()}

    for weekend_start, origin_map in weekend_origin_itins.items():
        for origin_label, itins in origin_map.items():
            buckets = collect_weekend_report(
                itineraries=itins,
                currency=CURRENCY,
                weeks=HORIZON_WEEKS,
                min_out_time=MIN_OUT_TIME,
                min_in_time=MIN_IN_TIME,
            )

            for ws, patterns in buckets.items():
                all_origins_buckets[origin_label].setdefault(ws, {})
                for pat, lines in patterns.items():
                    all_origins_buckets[origin_label][ws].setdefault(pat, [])
                    all_origins_buckets[origin_label][ws][pat].extend(lines)
                    all_origins_buckets[origin_label][ws][pat].sort(key=lambda x: x.price)
                    all_origins_buckets[origin_label][ws][pat] = all_origins_buckets[origin_label][ws][pat][:3]

    html = build_html_report(all_origins_buckets)
    send_email(subject="Weekend flight monitor (next 5 weeks)", html_body=html)
    print("Email sent.")


if __name__ == "__main__":
    main()
