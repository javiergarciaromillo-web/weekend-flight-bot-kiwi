from datetime import time, date, timedelta
from collections import defaultdict

from src.kiwi_fetch import fetch_round_trip_by_dates
from src.planner import Pattern, generate_date_pairs
from src.email_report import build_html_report, send_email
from src.report_builder import collect_weekend_report


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
    Pattern(name="thu_sun", depart_dow=3, return_dow=6),  # Thu->Sun
    Pattern(name="thu_mon", depart_dow=3, return_dow=0),  # Thu->Mon
    Pattern(name="fri_sun", depart_dow=4, return_dow=6),  # Fri->Sun
    Pattern(name="fri_mon", depart_dow=4, return_dow=0),  # Fri->Mon
]


def _pattern_title(pname: str) -> str:
    return {
        "thu_sun": "Thu → Sun",
        "thu_mon": "Thu → Mon",
        "fri_sun": "Fri → Sun",
        "fri_mon": "Fri → Mon",
    }.get(pname, pname)


def main():
    pairs = generate_date_pairs(HORIZON_WEEKS, PATTERNS)

    # weekend_start_thursday -> origin_label -> list[itineraries]
    weekend_origin_itins = defaultdict(lambda: defaultdict(list))

    for pname, dep, ret in pairs:
        # anchor week at Thursday (same as your Amadeus bot)
        anchor = dep if dep.weekday() == 3 else (dep - timedelta(days=1))

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

    # Convert to the structure expected by build_html_report:
    # origin_label -> weekend_start -> pattern -> lines
    all_origins_buckets = {k: {} for k in ORIGINS.keys()}

    for weekend_start, origin_map in weekend_origin_itins.items():
        for origin_label, itins in origin_map.items():
            # We reuse your existing report builder, but here we already know the horizon,
            # and we want time filtering and pattern grouping.
            buckets = collect_weekend_report(
                itineraries=itins,
                currency=CURRENCY,
                weeks=HORIZON_WEEKS,
                min_out_time=MIN_OUT_TIME,
                min_in_time=MIN_IN_TIME,
            )
            # buckets is weekend_start->pattern->lines; merge
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
