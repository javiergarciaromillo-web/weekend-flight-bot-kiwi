from datetime import date, datetime, time, timedelta
from collections import Counter

from dateutil import parser

from src.kiwi_fetch import fetch_round_trip


ORIGINS = {
    "AMS": "City:amsterdam_nl",
    "RTM": "City:rotterdam_nl",
}

DESTINATION = "City:barcelona_es"
CURRENCY = "EUR"
NIGHTS_QUERIES = [2, 3, 4]

MIN_TIME = time(17, 0)
WEEKS = 5


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


def _dep_local(leg: dict) -> datetime | None:
    seg = _first_segment(leg)
    if not seg:
        return None
    return _isoparse(((seg.get("source") or {}).get("localTime")))


def _pattern(out_dep: datetime, in_dep: datetime) -> str | None:
    # Mon=0 ... Sun=6
    o = out_dep.weekday()
    i = in_dep.weekday()
    if o == 4 and i == 6:
        return "Fri→Sun"
    if o == 3 and i == 6:
        return "Thu→Sun"
    if o == 4 and i == 0:
        return "Fri→Mon"
    if o == 3 and i == 0:
        return "Thu→Mon"
    return None


def _weekend_start_thu(out_dep: datetime) -> date:
    # If Fri, weekend start is previous Thu
    return (out_dep.date() - timedelta(days=1)) if out_dep.weekday() == 4 else out_dep.date()


def _within_next_weeks(d: date) -> bool:
    today = date.today()
    return today <= d <= (today + timedelta(days=7 * WEEKS))


def main():
    print("==== DEBUG RUN ====")
    print("Filter target:")
    print("- Outbound weekday in {Thu,Fri}")
    print("- Inbound weekday in {Sun,Mon}")
    print(f"- Outbound time >= {MIN_TIME.strftime('%H:%M')}")
    print(f"- Inbound time >= {MIN_TIME.strftime('%H:%M')}")
    print(f"- Weekend start within next {WEEKS} weeks\n")

    for origin_label, origin in ORIGINS.items():
        all_itins = []
        meta_out_days = Counter()
        meta_in_days = Counter()

        # 3 requests per origin
        for nights in NIGHTS_QUERIES:
            data = fetch_round_trip(
                source=origin,
                destination=DESTINATION,
                nights=nights,
                currency=CURRENCY,
                limit=200,
            )

            md = data.get("metadata") or {}
            for d in (md.get("outboundDays") or []):
                meta_out_days[d] += 1
            for d in (md.get("inboundDays") or []):
                meta_in_days[d] += 1

            itins = data.get("itineraries", []) or []
            all_itins.extend(itins)

        print(f"--- ORIGIN {origin_label} ---")
        print("Fetched itineraries total:", len(all_itins))
        if meta_out_days:
            print("metadata.outboundDays:", dict(meta_out_days))
        if meta_in_days:
            print("metadata.inboundDays:", dict(meta_in_days))

        # Parse deps
        parsed = []
        out_wd = Counter()
        in_wd = Counter()
        min_out = None
        max_out = None

        for it in all_itins:
            out_dep = _dep_local(it.get("outbound") or {})
            in_dep = _dep_local(it.get("inbound") or {})
            if out_dep is None or in_dep is None:
                continue

            parsed.append((it, out_dep, in_dep))

            out_wd[out_dep.strftime("%A")] += 1
            in_wd[in_dep.strftime("%A")] += 1

            min_out = out_dep if (min_out is None or out_dep < min_out) else min_out
            max_out = out_dep if (max_out is None or out_dep > max_out) else max_out

        print("Parsed with times:", len(parsed))
        if min_out and max_out:
            print("Outbound date range:", min_out.isoformat(), "->", max_out.isoformat())
        print("Outbound weekday distribution:", dict(out_wd))
        print("Inbound weekday distribution:", dict(in_wd))

        # Stepwise filters
        step0 = parsed
        step1 = [(it, o, i) for (it, o, i) in step0 if o.weekday() in (3, 4)]  # Thu/Fri
        step2 = [(it, o, i) for (it, o, i) in step1 if i.weekday() in (6, 0)]  # Sun/Mon
        step3 = [(it, o, i) for (it, o, i) in step2 if o.time() >= MIN_TIME and i.time() >= MIN_TIME]
        step4 = [(it, o, i) for (it, o, i) in step3 if _pattern(o, i) is not None]
        step5 = [(it, o, i) for (it, o, i) in step4 if _within_next_weeks(_weekend_start_thu(o))]

        print("\nFilter survival counts:")
        print("step0 parsed:", len(step0))
        print("step1 outbound Thu/Fri:", len(step1))
        print("step2 inbound Sun/Mon:", len(step2))
        print("step3 time >=17 both:", len(step3))
        print("step4 matches 4 patterns:", len(step4))
        print(f"step5 within next {WEEKS} weeks:", len(step5))

        # Show 3 examples if any remain at each step5
        if step5:
            step5_sorted = sorted(step5, key=lambda x: float(((x[0].get('price') or {}).get('amount') or "1e18")))
            print("\nExamples (up to 3) that PASS all filters:")
            for it, o, i in step5_sorted[:3]:
                price = float(((it.get("price") or {}).get("amount") or "nan"))
                print(f"- {price:.2f} {CURRENCY} | OUT {o} | IN {i}")
        print("\n")

    print("==== END DEBUG ====")


if __name__ == "__main__":
    main()
