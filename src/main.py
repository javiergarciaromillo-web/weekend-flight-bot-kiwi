from __future__ import annotations

import json
from dataclasses import asdict
from datetime import date
from pathlib import Path
from typing import Any, Dict, List, Optional

from jinja2 import Environment, FileSystemLoader, select_autoescape

from src.config import load_config
from src.flights_client import FlightsClient
from src.planner import generate_queries
from src.report import Offer, extract_offers_with_stats
from src.store import (
    Snapshot,
    get_meta,
    get_previous_best_price,
    init_db,
    set_meta,
    upsert_snapshot,
)
from src.mailer import send_email


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


def _pattern_label(p: str) -> str:
    return p.replace("_", "→")


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

    print(f"[INFO] run_date={run_date} last_refresh={last_refresh} do_refresh={do_refresh}")

    client = FlightsClient(cfg)
    queries = generate_queries(today=today, weeks=cfg.weeks)

    weekends_map: Dict[str, Dict[str, Dict[str, Any]]] = {}

    for q in queries:
        week_start_s = q.week_start.isoformat()
        week_end_s = q.inbound_date.isoformat()
        weekends_map.setdefault(week_start_s, {})

        for origin in cfg.origins:
            route_key = f"{origin}-{cfg.destination}"
            weekends_map[week_start_s].setdefault(route_key, {})

            outbound_s = q.outbound_date.isoformat()
            inbound_s = q.inbound_date.isoformat()

            offers: List[Offer] = []
            best_price: Optional[float] = None
            stats: Dict[str, Any] = {}

            if do_refresh:
                api = client.search_return(
                    origin=origin,
                    destination=cfg.destination,
                    departure_date=outbound_s,
                    return_date=inbound_s,
                    stops=cfg.direct_stops,
                    adults=1,
                )

                # DEBUG: inspect raw carriers for specific case
                if (
                    origin == "AMS"
                    and cfg.destination == "BCN"
                    and outbound_s == "2026-03-05"
                    and inbound_s == "2026-03-09"
                ):
                    data = (api.payload or {}).get("data") or {}
                    itins = data.get("itineraries") or []
                    carriers = set()
                    op_carriers = set()

                    for it in itins:
                        try:
                            out_seg = it["outbound"]["sectorSegments"][-1]["segment"]
                            in_seg = it["inbound"]["sectorSegments"][-1]["segment"]

                            c1 = ((out_seg.get("carrier") or {}).get("code")) or "?"
                            c2 = ((in_seg.get("carrier") or {}).get("code")) or "?"
                            oc1 = ((out_seg.get("operatingCarrier") or {}).get("code")) or "?"
                            oc2 = ((in_seg.get("operatingCarrier") or {}).get("code")) or "?"

                            carriers.update([c1, c2])
                            op_carriers.update([oc1, oc2])
                        except Exception:
                            pass

                    print(f"[DEBUG] carriers(carrier.code)={sorted(carriers)}")
                    print(f"[DEBUG] carriers(operatingCarrier.code)={sorted(op_carriers)}")

                offers, stats = extract_offers_with_stats(
                    api.payload,
                    cfg.out_time_from,
                    cfg.out_time_to,
                    cfg.out_time_mode,
                    cfg.in_time_from,
                    cfg.in_time_to,
                    cfg.in_time_mode,
                )

                # DEBUG: show filtered offers
                if (
                    origin == "AMS"
                    and cfg.destination == "BCN"
                    and outbound_s == "2026-03-05"
                    and inbound_s == "2026-03-09"
                ):
                    print("[DEBUG] Filtered offers (first 10):")
                    for i, o in enumerate(offers[:10], start=1):
                        print(
                            f"  {i}) €{o.price_eur:.2f} "
                            f"OUT {o.flight_out} {o.depart_out}-{o.arrive_out} "
                            f"| IN {o.flight_in} {o.depart_in}-{o.arrive_in}"
                        )

                offers = offers[: cfg.top_n]
                best_price = offers[0].price_eur if offers else None

                print(
                    f"[API] {origin}->{cfg.destination} {outbound_s}/{inbound_s} "
                    f"status={api.status_code} total={stats.get('totalResultCount')} "
                    f"itins={stats.get('itineraries_len')} parsed={stats.get('parsed_total')} "
                    f"out_ok={stats.get('out_ok')} in_ok={stats.get('in_ok')} both_ok={stats.get('both_ok')} "
                    f"out_mode={stats.get('out_mode')} in_mode={stats.get('in_mode')} "
                    f"examples={stats.get('examples')}"
                )

            snapshot = Snapshot(
                run_date=run_date,
                origin=origin,
                destination=cfg.destination,
                pattern=q.pattern,
                outbound_date=outbound_s,
                inbound_date=inbound_s,
                best_price_eur=best_price,
                offers_json=json.dumps([asdict(o) for o in offers], ensure_ascii=False),
                last_updated=last_refresh or run_date,
            )
            upsert_snapshot(snapshot)

    subject = f"{cfg.subject_base} | {run_date}"
    send_email(
        smtp_host=cfg.smtp_host,
        smtp_port=cfg.smtp_port,
        smtp_user=cfg.smtp_user,
        smtp_pass=cfg.smtp_pass,
        to_addr=cfg.email_to,
        subject=subject,
        html_body="<p>Debug run completed</p>",
    )


if __name__ == "__main__":
    main()
