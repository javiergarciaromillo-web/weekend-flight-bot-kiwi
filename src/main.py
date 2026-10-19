from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path
from zoneinfo import ZoneInfo

from src.planner import generate_weekend_pairs
from src.holidays import generate_holiday_pairs
from src.scrapers.google_flights_ui import search_google_flights, recover_failed_queries
from src.report import build_html_report
from src.emailer import send_email_html
from src.store import init_db, save_weekend_snapshot, get_latest_learning_opportunities
from src.store import save_flight_observations, record_booking_decisions
from src.learning import run_learning_sampling


def main() -> None:
    run_date = datetime.now(ZoneInfo("Europe/Amsterdam")).date()

    init_db()

    print("[INFO] Generating weekend pairs...")
    pairs = generate_weekend_pairs(
        start_date=run_date,
        weeks=7,
        skip_weeks=1,
    )

    pairs = sorted(set(pairs + generate_holiday_pairs(run_date)))

    print("[INFO] Scraping operational flights...")
    diagnostics = {}
    rows = search_google_flights(pairs, diagnostics=diagnostics)

    print("[INFO] Running learning engine before report...")
    learning_diagnostics = {}
    learning_rows = run_learning_sampling(run_date, diagnostics=learning_diagnostics)
    rows = recover_failed_queries(pairs, rows, diagnostics, learning_rows, learning_diagnostics)

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

    all_diagnostics = {**learning_diagnostics, **diagnostics}
    save_flight_observations(run_date, learning_rows + rows, all_diagnostics)
    decisions = record_booking_decisions(run_date, rows, pairs, diagnostics)

    print("[INFO] Building report...")
    html = build_html_report(run_date, rows, pairs=pairs, diagnostics=diagnostics, decisions=decisions)

    # Retain the exact report and source observations for review from this chat.
    report_dir = Path('data/report')
    report_dir.mkdir(parents=True, exist_ok=True)
    (report_dir / 'report.html').write_text(html, encoding='utf-8')
    (report_dir / 'report.json').write_text(json.dumps({
        'schema_version': 2,
        'run_date': run_date,
        'pairs': pairs,
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
