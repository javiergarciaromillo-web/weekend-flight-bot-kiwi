from __future__ import annotations

from datetime import date

from src.planner import generate_weekend_pairs
from src.scrapers.google_flights_ui import search_google_flights
from src.store import init_db, store_options
from src.report import build_html_report
from src.emailer import send_email_html


def main() -> None:
    run_date = date.today()

    pairs = generate_weekend_pairs(run_date, 5)

    results = search_google_flights(pairs)

    init_db()
    store_options(run_date, results)

    html = build_html_report(run_date, results)

    send_email_html(
        subject=f"Weekend Flights {run_date.isoformat()}",
        html_body=html,
    )

    print("Flights found:", len(results))


if __name__ == "__main__":
    main()
