from __future__ import annotations

from datetime import date, timedelta

from src.scrapers.google_flights_ui import search_google_flights
from src.store import save_learning_snapshot


OFFSETS = [30, 45, 60, 75, 90, 120, 150]


def _next_weekday(base: date, weekday: int) -> date:
    """
    weekday:
    Monday=0 ... Sunday=6
    """
    days_ahead = (weekday - base.weekday()) % 7
    if days_ahead == 0:
        days_ahead = 7
    return base + timedelta(days=days_ahead)


def _build_pairs_for_offset(run_date: date, offset: int):
    base = run_date + timedelta(days=offset)

    thu = _next_weekday(base, 3)
    fri = _next_weekday(base, 4)

    sun_from_thu = thu + timedelta(days=3)
    mon_from_thu = thu + timedelta(days=4)

    sun_from_fri = fri + timedelta(days=2)
    mon_from_fri = fri + timedelta(days=3)

    return [
        ("THU-SUN", thu, sun_from_thu),
        ("THU-MON", thu, mon_from_thu),
        ("FRI-SUN", fri, sun_from_fri),
        ("FRI-MON", fri, mon_from_fri),
    ]


def run_learning_sampling(run_date: date):
    print("[INFO] Starting learning sampling...")

    for offset in OFFSETS:
        patterns = _build_pairs_for_offset(run_date, offset)

        for pattern_name, outbound, inbound in patterns:
            try:
                rows = search_google_flights([(outbound, inbound)])

                outbound_rows = [r for r in rows if r["leg_type"] == "outbound"]
                inbound_rows = [r for r in rows if r["leg_type"] == "inbound"]

                best_out = min([r["price"] for r in outbound_rows], default=None)
                best_in = min([r["price"] for r in inbound_rows], default=None)

                best_combo = None
                if best_out is not None and best_in is not None:
                    best_combo = best_out + best_in

                save_learning_snapshot(
                    run_date=run_date,
                    sample_name=f"{offset}_{pattern_name}",
                    outbound=outbound,
                    inbound=inbound,
                    days_to_departure=(outbound - run_date).days,
                    pattern=pattern_name,
                    best_outbound=best_out,
                    best_inbound=best_in,
                    best_combo=best_combo,
                )

                print(
                    f"[INFO] Learning saved {offset}d {pattern_name} "
                    f"combo={best_combo}"
                )

            except Exception as e:
                print(f"[ERROR] Learning {offset} {pattern_name}: {e}")
