from __future__ import annotations

from datetime import date, datetime
from pathlib import Path

import yaml

from src.emailer import send_email_html
from src.filters import filter_options
from src.models import Route, SearchConfig
from src.planner import next_n_weeks_weekend_pairs
from src.report import build_html_report
from src.scrapers.skyscanner import scrape_skyscanner
from src.store import init_db, store_options


def load_config() -> tuple[SearchConfig, list[Route]]:
    cfg_path = Path("config/routes.yaml")
    raw = yaml.safe_load(cfg_path.read_text())

    min_departure_time = datetime.strptime(
        raw["search"]["min_departure_time"], "%H:%M"
    ).time()

    search_cfg = SearchConfig(
        weeks_ahead=raw["search"]["weeks_ahead"],
        outbound_days=raw["search"]["outbound_days"],
        inbound_days=raw["search"]["inbound_days"],
        min_departure_time=min_departure_time,
        direct_only=raw["search"]["direct_only"],
        allowed_airlines=raw["search"]["allowed_airlines"],
    )

    routes = [
        Route(origin=item["origin"], destination=item["destination"])
        for item in raw["routes"]
    ]

    return search_cfg, routes


def main() -> None:
    run_date = date.today()

    search_cfg, routes = load_config()

    pairs = next_n_weeks_weekend_pairs(
        start_date=run_date,
        weeks_ahead=search_cfg.weeks_ahead,
        outbound_days=search_cfg.outbound_days,
        inbound_days=search_cfg.inbound_days,
    )

    init_db()

    raw_options = scrape_skyscanner(routes, pairs)

    filtered_options = filter_options(raw_options, search_cfg)

    store_options(run_date, filtered_options)

    html = build_html_report(run_date, filtered_options)

    subject = f"Weekend Flight Bot - {run_date.isoformat()}"

    send_email_html(subject, html)

    print("Flights scraped:", len(filtered_options))


if __name__ == "__main__":
    main()
