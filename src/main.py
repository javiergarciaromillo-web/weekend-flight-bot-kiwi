from __future__ import annotations

from datetime import date

from src.dates import generate_pairs
from src.scrapers.google_flights_ui import search_google_flights
from src.report import build_html_report
from src.mailer import send_email
from src.store import init_db, save_weekend_snapshot
from src.learning import run_learning_sampling


def main():
    run_date = date.today()

    init_db()

    print("[INFO] Generating weekend pairs...")
    pairs = generate_pairs(7)

    print("[INFO] Scraping operational flights...")
    rows = search_google_flights(pairs)

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

    print("[INFO] Building report...")
    html = build_html_report(run_date, rows)

    print("[INFO] Sending email...")
    send_email(
        subject=f"Weekend Flight Report {run_date.isoformat()}",
        html=html,
    )

    print("[INFO] Running learning engine...")
    run_learning_sampling(run_date)

    print("[INFO] Finished.")


if __name__ == "__main__":
    main()
