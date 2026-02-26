from __future__ import annotations

import json
import os
from dataclasses import asdict
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List

from jinja2 import Environment, FileSystemLoader, select_autoescape

from src.config import load_config
from src.flights_client import FlightsClient
from src.planner import QueryKey, generate_queries
from src.report import Offer, extract_offers
from src.store import (
    Snapshot,
    get_meta,
    get_previous_best_price,
    init_db,
    set_meta,
    upsert_snapshot,
)
from src.mailer import send_email


def _today_str() -> str:
    return date.today().isoformat()


def _should_refresh(today: date, last_refresh: str | None, every_days: int) -> bool:
    if not last_refresh:
        return True
    try:
        lr = date.fromisoformat(last_refresh)
    except Exception:
        return True
    return (today - lr).days >= every_days


def _render_email(template_path: str, ctx: Dict[str, Any]) -> str:
    env = Environment(
        loader=FileSystemLoader(str(Path(template_path).parent)),
        autoescape=select_autoescape(["html"]),
    )
    tpl = env.get_template(Path(template_path).name)
    return tpl.render(**ctx)


def main() -> None:
    cfg = load_config()
    init_db()

    today = date.today()
    run_date = today.isoformat()

    last_refresh = get_meta("last_refresh_date")
    do_refresh = _should_refresh(today, last_refresh, cfg.refresh_every_days)
    if do_refresh:
        last_refresh = run_date
        set_meta("last_refresh_date", last_refresh)

    client = FlightsClient(cfg)

    # Build date patterns (origin/destination set later)
    base_queries = generate_queries(today=today, weeks=cfg.weeks)

    blocks: List[Dict[str, Any]] = []
    last_updated_for_email = last_refresh or run_date

    for origin in cfg.origins:
        for q in base_queries:
            qk = QueryKey(
                origin=origin,
                destination=cfg.destination,
                pattern=q.pattern,
                outbound_date=q.outbound_date,
                inbound_date=q.inbound_date,
            )

            outbound_s = qk.outbound_date.isoformat()
            inbound_s = qk.inbound_date.isoformat()

            offers: List[Offer] = []
            api_payload: Dict[str, Any] | None = None

            if do_refresh:
                api = client.search_return(
                    origin=qk.origin,
                    destination=qk.destination,
                    departure_date=outbound_s,
                    return_date=inbound_s,
                    stops=cfg.direct_stops,
                    adults=1,
                )
                api_payload = api.payload
                offers = extract_offers(api_payload, cfg.time_from, cfg.time_to)[: cfg.top_n]
            else:
                # No refresh today: we will not hit API.
                # We keep offers empty here and rely on "previous run delta" only when refreshed.
                # Email still goes out, indicating last refresh date.
                offers = []

            best_price = offers[0].price_eur if offers else None

            # Persist snapshot for TODAY:
            # - If no refresh, we store empty offers and best_price None to avoid misleading deltas.
            #   The email will say "Last API refresh: X".
            # If you prefer to resend the last known offers, we can add a "carry-forward" mode later.
            snapshot = Snapshot(
                run_date=run_date,
                origin=qk.origin,
                destination=qk.destination,
                pattern=qk.pattern,
                outbound_date=outbound_s,
                inbound_date=inbound_s,
                best_price_eur=best_price,
                offers_json=json.dumps([asdict(o) for o in offers], ensure_ascii=False),
                last_updated=last_updated_for_email,
            )
            upsert_snapshot(snapshot)

            prev_best = get_previous_best_price(
                origin=qk.origin,
                destination=qk.destination,
                pattern=qk.pattern,
                outbound_date=outbound_s,
                inbound_date=inbound_s,
                run_date=run_date,
            )

            delta = None
            if best_price is not None and prev_best is not None:
                delta = float(best_price) - float(prev_best)

            title = f"{qk.origin} ↔ {qk.destination} | {qk.pattern.replace('_', '→')}"
            subtitle = f"{outbound_s} to {inbound_s}"

            blocks.append(
                {
                    "title": title,
                    "subtitle": subtitle,
                    "best": offers[0] if offers else None,
                    "top": offers,
                    "delta": delta,
                }
            )

    html = _render_email(
        "templates/email.html",
        {
            "subject": cfg.subject,
            "header": f"{','.join(cfg.origins)} ↔ {cfg.destination}",
            "time_from": cfg.time_from,
            "time_to": cfg.time_to,
            "weeks": cfg.weeks,
            "top_n": cfg.top_n,
            "run_date": run_date,
            "last_updated": last_updated_for_email,
            "blocks": blocks,
        },
    )

    send_email(
        smtp_host=cfg.smtp_host,
        smtp_port=cfg.smtp_port,
        smtp_user=cfg.smtp_user,
        smtp_pass=cfg.smtp_pass,
        to_addr=cfg.email_to,
        subject=cfg.subject,
        html_body=html,
    )


if __name__ == "__main__":
    main()
