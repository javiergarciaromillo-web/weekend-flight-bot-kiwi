from __future__ import annotations

from datetime import date, timedelta

from src.scrapers.google_flights_ui import search_google_flights
from src.store import save_learning_snapshot


OFFSETS = [30, 45, 60, 75, 90, 120, 150]


def _next_weekday(base: date, weekday: int) -> date:
    days_ahead = (weekday - base.weekday()) % 7
    if days_ahead == 0:
        days_ahead = 7
    return base + timedelta(days=days_ahead)


def _build_pairs_for_offset(run_date: date, offset: int):
    base = run_date + timedelta(days=offset)

    thu = _next_weekday(base, 3)
    fri = _next_weekday(base, 4)

    return [
        ("THU-SUN", thu, thu + timedelta(days=3)),
        ("THU-MON", thu, thu + timedelta(days=4)),
        ("FRI-SUN", fri, fri + timedelta(days=2)),
        ("FRI-MON", fri, fri + timedelta(days=3)),
    ]


def _best_row(rows: list[dict]) -> dict | None:
    if not rows:
        return None
    return sorted(rows, key=lambda r: r["price"])[0]


def run_learning_sampling(run_date: date):
    print("[INFO] Starting learning sampling...")

    for offset in OFFSETS:
        patterns = _build_pairs_for_offset(run_date, offset)

        for pattern_name, outbound, inbound in patterns:
            try:
                rows = search_google_flights(
                    [(outbound, inbound)],
                    allow_klm_from_ams=True,
                )

                outbound_rows = [r for r in rows if r["leg_type"] == "outbound"]
                inbound_rows = [r for r in rows if r["leg_type"] == "inbound"]

                best_out_row = _best_row(outbound_rows)
                best_in_row = _best_row(inbound_rows)

                best_out = best_out_row["price"] if best_out_row else None
                best_in = best_in_row["price"] if best_in_row else None

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
                    outbound_origin=best_out_row.get("origin") if best_out_row else None,
                    outbound_destination=best_out_row.get("destination") if best_out_row else None,
                    outbound_airline=best_out_row.get("airline") if best_out_row else None,
                    outbound_departure_time=best_out_row.get("outbound_departure") if best_out_row else None,
                    outbound_arrival_time=best_out_row.get("outbound_arrival") if best_out_row else None,
                    outbound_source_url=best_out_row.get("source_url") if best_out_row else None,
                    inbound_origin=best_in_row.get("origin") if best_in_row else None,
                    inbound_destination=best_in_row.get("destination") if best_in_row else None,
                    inbound_airline=best_in_row.get("airline") if best_in_row else None,
                    inbound_departure_time=best_in_row.get("outbound_departure") if best_in_row else None,
                    inbound_arrival_time=best_in_row.get("outbound_arrival") if best_in_row else None,
                    inbound_source_url=best_in_row.get("source_url") if best_in_row else None,
                )

                print(
                    f"[INFO] Learning saved {offset}d {pattern_name} "
                    f"combo={best_combo}"
                )

            except Exception as e:
                print(f"[ERROR] Learning {offset} {pattern_name}: {e}")
