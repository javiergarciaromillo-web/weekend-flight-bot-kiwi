from __future__ import annotations

import json
from dataclasses import asdict
from datetime import date
from pathlib import Path
from typing import Any, Dict, List, Optional

from jinja2 import Environment, FileSystemLoader, select_autoescape

from src.config import load_config
from src.flights_client import FlightsClient
from src.planner import QueryKey, generate_queries
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

    # weekends_map[week_start][route_key][pattern] = payload for template
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
                offers, stats = extract_offers_with_stats(api.payload, cfg.time_from, cfg.time_to)
                offers = offers[: cfg.top_n]
                best_price = offers[0].price_eur if offers else None

                print(
                    f"[API] {origin}->{cfg.destination} {outbound_s}/{inbound_s} "
                    f"status={api.status_code} total={stats.get('totalResultCount')} "
                    f"itins={stats.get('itineraries_len')} parsed={stats.get('parsed_total')} "
                    f"time_ok={stats.get('time_ok')} examples={stats.get('examples')}"
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

            prev_best = get_previous_best_price(
                origin=origin,
                destination=cfg.destination,
                pattern=q.pattern,
                outbound_date=outbound_s,
                inbound_date=inbound_s,
                run_date=run_date,
            )
            delta = None
            if best_price is not None and prev_best is not None:
                delta = float(best_price) - float(prev_best)

            weekends_map[week_start_s][route_key][q.pattern] = {
                "pattern_label": _pattern_label(q.pattern),
                "outbound_date": outbound_s,
                "inbound_date": inbound_s,
                "best": offers[0] if offers else None,
                "top": offers,
                "delta": delta,
                "week_end": week_end_s,
            }

    # Build template-friendly list (sorted)
    weekends: List[Dict[str, Any]] = []
    for week_start_s in sorted(weekends_map.keys()):
        routes_out: List[Dict[str, Any]] = []
        best_overall: Optional[float] = None

        for route_key in sorted(weekends_map[week_start_s].keys()):
            patterns_dict = weekends_map[week_start_s][route_key]

            ordered = ["THU_SUN", "THU_MON", "FRI_SUN", "FRI_MON"]
            patterns_list: List[Dict[str, Any]] = []
            for p in ordered:
                if p in patterns_dict:
                    patterns_list.append(patterns_dict[p])
                    b = patterns_dict[p].get("best")
                    if b and (best_overall is None or b.price_eur < best_overall):
                        best_overall = b.price_eur

            routes_out.append(
                {
                    "route_label": route_key.replace("-", " ↔ "),
                    "patterns": patterns_list,
                }
            )

        any_route = next(iter(weekends_map[week_start_s].values()))
        any_pat = next(iter(any_route.values()))
        week_end_s = any_pat["week_end"]

        weekends.append(
            {
                "week_start": week_start_s,
                "week_end": week_end_s,
                "best_label": f"€{best_overall:.2f}" if best_overall is not None else "—",
                "routes": routes_out,
            }
        )

    html = _render_email(
        "templates/email.html",
        {
            "subject": cfg.subject_base,
            "header": f"{','.join(cfg.origins)} ↔ {cfg.destination}",
            "time_from": cfg.time_from,
            "time_to": cfg.time_to,
            "weeks": cfg.weeks,
            "run_date": run_date,
            "last_updated": last_refresh or run_date,
            "weekends": weekends,
        },
    )

    subject = f"{cfg.subject_base} | {run_date}"

    send_email(
        smtp_host=cfg.smtp_host,
        smtp_port=cfg.smtp_port,
        smtp_user=cfg.smtp_user,
        smtp_pass=cfg.smtp_pass,
        to_addr=cfg.email_to,
        subject=subject,
        html_body=html,
    )


if __name__ == "__main__":
    main()
