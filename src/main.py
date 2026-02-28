from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any, Dict, List

from jinja2 import Environment, FileSystemLoader, select_autoescape

from src.config import Config, WatchItem, load_config
from src.history import get_prev_price, make_key, set_last_price
from src.mailer import send_email
from src.planner import WeekendWindow, generate_weekend_windows
from src.scrape_transavia import scrape_transavia_price
from src.scrape_vueling import scrape_vueling_price


def _render_email(template_path: str, ctx: Dict[str, Any]) -> str:
    env = Environment(
        loader=FileSystemLoader(str(Path(template_path).parent)),
        autoescape=select_autoescape(["html"]),
    )
    tpl = env.get_template(Path(template_path).name)
    return tpl.render(**ctx)


def _date_for_weekday(w: WeekendWindow, weekday: str) -> date:
    return {
        "THU": w.thu,
        "FRI": w.fri,
        "SUN": w.sun,
        "MON": w.mon,
    }[weekday]


def _block_title(weekday: str) -> str:
    return {
        "THU": "Thursday outbound",
        "FRI": "Friday outbound",
        "SUN": "Sunday return",
        "MON": "Monday return",
    }[weekday]


def _run_item(cfg: Config, item: WatchItem, dep_date: str) -> Dict[str, Any]:
    if item.provider == "VUELING":
        res = scrape_vueling_price(
            origin=item.origin,
            destination=item.destination,
            date_iso=dep_date,
            flight_code=item.flight_code,
            time_from=cfg.time_from,
            time_to=cfg.time_to,
        )
    else:
        res = scrape_transavia_price(
            origin=item.origin,
            destination=item.destination,
            date_iso=dep_date,
            flight_code=item.flight_code,
            time_from=cfg.time_from,
            time_to=cfg.time_to,
        )

    key = make_key(item.provider, item.origin, item.destination, dep_date, item.flight_code)
    prev = get_prev_price(key)

    price = res.get("price_eur")
    delta = None
    if price is not None and prev is not None:
        delta = float(price) - float(prev)

    # Update history (only if we got a price)
    set_last_price(key, price)

    return {
        "provider": item.provider,
        "origin": item.origin,
        "destination": item.destination,
        "date": dep_date,
        "flight_code": item.flight_code,
        "depart": res.get("depart") or "—",
        "arrive": res.get("arrive") or "—",
        "price_eur": price,
        "delta": delta,
        "error": res.get("error"),
    }


def main() -> None:
    cfg = load_config()
    today = date.today()
    run_date = today.isoformat()

    weekends = generate_weekend_windows(today=today, weeks=cfg.weeks)

    email_weekends: List[Dict[str, Any]] = []

    for w in weekends:
        blocks: List[Dict[str, Any]] = []

        for weekday in ["THU", "FRI", "SUN", "MON"]:
            d = _date_for_weekday(w, weekday).isoformat()
            items = [x for x in cfg.watchlist if x.weekday == weekday]

            lines = []
            for it in items:
                r = _run_item(cfg, it, d)
                lines.append(r)
                print(
                    f"[SCRAPE] {it.provider} {it.origin}->{it.destination} {d} {it.flight_code} "
                    f"price={r.get('price_eur')} depart={r.get('depart')} err={r.get('error')}"
                )

            blocks.append(
                {
                    "title": _block_title(weekday),
                    "date": d,
                    "items": lines,
                }
            )

        email_weekends.append(
            {
                "week_start": w.week_start.isoformat(),
                "thu": w.thu.isoformat(),
                "fri": w.fri.isoformat(),
                "sun": w.sun.isoformat(),
                "mon": w.mon.isoformat(),
                "blocks": blocks,
            }
        )

    html = _render_email(
        "templates/email.html",
        {
            "subject": cfg.subject_base,
            "header": "AMS/RTM ↔ BCN (Vueling/Transavia watchlist)",
            "weeks": cfg.weeks,
            "time_from": cfg.time_from,
            "time_to": cfg.time_to,
            "tz_name": str(cfg.tz),
            "run_date": run_date,
            "weekends": email_weekends,
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
