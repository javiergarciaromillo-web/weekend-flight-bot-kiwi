from __future__ import annotations

from datetime import date, datetime
import json
from pathlib import Path
from zoneinfo import ZoneInfo

from src.horizon import monitoring_plan
from src.scrapers.google_flights_ui import search_google_flights
from src.report import build_html_report
from src.emailer import send_email_html
from src.store import init_db, save_weekend_snapshot, get_latest_learning_opportunities, get_horizon_tracking
from src.store import save_flight_observations, record_booking_decisions
from src.family import joined_pairs, load_plan
from src.learning import save_sampled_weekends


def main() -> None:
    run_date = datetime.now(ZoneInfo("Europe/Amsterdam")).date()

    init_db()
    family_plan = load_plan()

    # Search the family period even before it enters the usual seven-week horizon.
    planning_start = max(run_date, date.fromisoformat(family_plan['required_from'])) if family_plan.get('required_from') else run_date

    print("[INFO] Planning rolling 300-day fare monitoring...")
    baseline_pairs, visible_saturdays, daily_saturdays, sampled_saturdays = monitoring_plan(
        run_date, planning_start,
    )
    # Long stays over adjacent weekends reuse only the departure/return dates
    # already selected today; no extra distant dates are queried off schedule.
    pairs = sorted(set(baseline_pairs + joined_pairs(baseline_pairs)))
    print(f"[INFO] Monitoring {len(visible_saturdays)} weekends, "
          f"sampling {len(sampled_saturdays)} today ({len(daily_saturdays)} daily), "
          f"{len(pairs)} travel combinations")

    print("[INFO] Scraping scheduled flight dates once...")
    diagnostics = {}
    rows = search_google_flights(pairs, diagnostics=diagnostics)

    # Save and report only the final observations after all recovery attempts.
    for outbound, inbound in pairs:
        weekend_rows = [
            r for r in rows
            if r["outbound"] == outbound and r["inbound"] == inbound
        ]

        outbound_rows = [r for r in weekend_rows if r["leg_type"] == "outbound"]
        inbound_rows = [r for r in weekend_rows if r["leg_type"] == "inbound"]

        best_out = min([r["price"] for r in outbound_rows], default=None)
        best_in = min([r["price"] for r in inbound_rows], default=None)

        best_combo = None
        if best_out is not None and best_in is not None:
            best_combo = best_out + best_in

        save_weekend_snapshot(
            run_date=run_date,
            outbound=outbound,
            inbound=inbound,
            best_outbound=best_out,
            best_inbound=best_in,
            best_combo=best_combo,
        )

    save_sampled_weekends(run_date, rows, baseline_pairs, daily_saturdays=daily_saturdays)
    save_flight_observations(run_date, rows, diagnostics)
    decisions = record_booking_decisions(run_date, rows, pairs, diagnostics)

    print("[INFO] Building report...")
    radar = get_horizon_tracking(visible_saturdays)
    html = build_html_report(run_date, rows, pairs=pairs, diagnostics=diagnostics,
                             decisions=decisions, family_plan=family_plan,
                             horizon_tracking=radar, daily_saturdays=daily_saturdays)

    # Retain the exact report and source observations for review from this chat.
    report_dir = Path('data/report')
    report_dir.mkdir(parents=True, exist_ok=True)
    (report_dir / 'report.html').write_text(html, encoding='utf-8')
    (report_dir / 'report.json').write_text(json.dumps({
        'schema_version': 3,
        'run_date': run_date,
        'pairs': pairs,
        'family_plan': family_plan,
        'monitoring_days': 300,
        'daily_weekends': daily_saturdays,
        'sampled_weekends_today': sampled_saturdays,
        'horizon_tracking': radar,
        'flights': rows,
        'decisions': [dict(outbound=o, inbound=i, **d) for (o, i), d in decisions.items()],
        'queries': [dict(origin=o, destination=d, date=day, status=status)
                    for (o, d, day), status in diagnostics.items()],
        'learning': [o for o in get_latest_learning_opportunities(limit=100)
                     if o['run_date'] == str(run_date)],
    }, default=str, ensure_ascii=False, indent=2), encoding='utf-8')

    print("[INFO] Sending email...")
    send_email_html(
        subject=f"Weekend Flight Report {run_date.isoformat()}",
        html_body=html,
    )

    print("[INFO] Finished.")


if __name__ == "__main__":
    main()
