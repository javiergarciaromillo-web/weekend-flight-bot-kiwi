from __future__ import annotations

from collections import defaultdict
from datetime import date

from src.store import get_weekend_history


WEEKDAY_LABELS = {
    0: "Mon",
    1: "Tue",
    2: "Wed",
    3: "Thu",
    4: "Fri",
    5: "Sat",
    6: "Sun",
}


def _day_label(d: date) -> str:
    return f"{WEEKDAY_LABELS[d.weekday()]} {d.isoformat()}"


def _fmt_price(value: float | None) -> str:
    return "—" if value is None else f"{value:.2f} €"


def _price_delta(current: float | None, previous: float | None) -> str:
    if current is None:
        return "—"
    if previous is None:
        return "new"

    diff = round(current - previous, 2)

    if diff == 0:
        return "0.00 €"
    if diff > 0:
        return f"+{diff:.2f} €"
    return f"{diff:.2f} €"


def _trend_label(current: float | None, historical_min: float | None) -> str:
    if current is None or historical_min is None or historical_min <= 0:
        return "Too early to tell"

    ratio = current / historical_min

    if ratio <= 1.03:
        return "Buy now"
    if ratio <= 1.08:
        return "Probably buy soon"
    if ratio <= 1.18:
        return "Watch closely"
    return "Too early to tell"


def _group_rows(rows: list[dict]) -> dict[tuple[date, date], dict[str, dict[str, list[dict]]]]:
    grouped: dict[tuple[date, date], dict[str, dict[str, list[dict]]]] = {}

    for row in rows:
        weekend_key = (row["outbound"], row["inbound"])
        grouped.setdefault(
            weekend_key,
            {
                "outbound": defaultdict(list),
                "inbound": defaultdict(list),
            },
        )

        leg_type = row.get("leg_type", "outbound")
        route_key = f"{row['origin']} → {row['destination']}"
        grouped[weekend_key][leg_type][route_key].append(row)

    for weekend_key in grouped:
        for leg_type in ["outbound", "inbound"]:
            for route_key in grouped[weekend_key][leg_type]:
                grouped[weekend_key][leg_type][route_key] = sorted(
                    grouped[weekend_key][leg_type][route_key],
                    key=lambda r: (
                        r["price"],
                        r.get("outbound_departure", "99:99"),
                    ),
                )[:3]

    return grouped


def _best_price(rows: list[dict]) -> float | None:
    if not rows:
        return None
    return min(row["price"] for row in rows)


def _best_combo_price(outbound_rows: list[dict], inbound_rows: list[dict]) -> float | None:
    best_out = _best_price(outbound_rows)
    best_in = _best_price(inbound_rows)

    if best_out is None or best_in is None:
        return None

    return best_out + best_in


def _find_previous_and_history(
    weekend_outbound: date,
    weekend_inbound: date,
) -> dict[str, float | None]:
    history = get_weekend_history(weekend_outbound, weekend_inbound)

    if not history:
        return {
            "outbound_today": None,
            "inbound_today": None,
            "combo_today": None,
            "outbound_prev": None,
            "inbound_prev": None,
            "combo_prev": None,
            "outbound_hist_min": None,
            "inbound_hist_min": None,
            "combo_hist_min": None,
            "history_rows": [],
        }

    today_row = history[-1]
    prev_row = history[-2] if len(history) >= 2 else None

    outbound_hist_values = [r["best_outbound"] for r in history if r["best_outbound"] is not None]
    inbound_hist_values = [r["best_inbound"] for r in history if r["best_inbound"] is not None]
    combo_hist_values = [r["best_combo"] for r in history if r["best_combo"] is not None]

    return {
        "outbound_today": today_row["best_outbound"],
        "inbound_today": today_row["best_inbound"],
        "combo_today": today_row["best_combo"],
        "outbound_prev": prev_row["best_outbound"] if prev_row else None,
        "inbound_prev": prev_row["best_inbound"] if prev_row else None,
        "combo_prev": prev_row["best_combo"] if prev_row else None,
        "outbound_hist_min": min(outbound_hist_values) if outbound_hist_values else None,
        "inbound_hist_min": min(inbound_hist_values) if inbound_hist_values else None,
        "combo_hist_min": min(combo_hist_values) if combo_hist_values else None,
        "history_rows": history[-7:],
    }


def _build_route_table(rows: list[dict], route_title: str) -> str:
    if not rows:
        return f"""
          <div style="padding:6px 0 10px 0;">
            <div style="font-size:13px; color:#666; font-weight:700;">{route_title}</div>
            <div style="margin-top:4px; font-size:12px; color:#999;">No options found.</div>
          </div>
        """

    html = f"""
      <div style="padding:6px 0 10px 0;">
        <div style="font-size:13px; font-weight:700; color:#222;">{route_title}</div>
    """

    for idx, item in enumerate(rows, start=1):
        html += f"""
          <div style="margin-top:8px; padding:8px 10px; border:1px solid #ececec; border-radius:6px; background:#fff;">
            <div style="font-size:13px; font-weight:700; line-height:1.35;">
              {idx}) {item.get('airline', 'Unknown')} — {item['price']:.2f} €
            </div>
            <div style="margin-top:3px; font-size:12px; color:#333;">
              {item.get('outbound_departure', 'N/A')} → {item.get('outbound_arrival', 'N/A')}
            </div>
            <div style="margin-top:3px; font-size:11px; color:#777;">
              Flight no: {item.get('outbound_flight_no', 'N/A')}
            </div>
          </div>
        """

    html += "</div>"
    return html


def _build_leg_column(
    title: str,
    day_label: str,
    grouped_routes: dict[str, list[dict]],
) -> str:
    html = f"""
      <td style="width:50%; vertical-align:top; padding:12px 14px; border-left:1px solid #eee;">
        <div style="font-size:16px; font-weight:700; color:#111;">{title}</div>
        <div style="margin-top:3px; font-size:12px; color:#666;">{day_label}</div>
    """

    if not grouped_routes:
        html += """
        <div style="margin-top:10px; font-size:12px; color:#999;">No options found.</div>
        """
    else:
        for route_key in sorted(grouped_routes.keys()):
            html += _build_route_table(grouped_routes[route_key], route_key)

    html += "</td>"
    return html


def _build_history_table(summary: dict[str, float | None]) -> str:
    history_rows = summary.get("history_rows", [])

    if not history_rows:
        return """
          <div style="padding:14px 18px; border-top:1px solid #ececec;">
            <div style="font-size:14px; font-weight:700;">Trend summary</div>
            <div style="margin-top:6px; font-size:12px; color:#888;">No historical data yet.</div>
          </div>
        """

    html = f"""
      <div style="padding:14px 18px; border-top:1px solid #ececec;">
        <div style="font-size:14px; font-weight:700;">Trend summary</div>
        <div style="margin-top:8px; font-size:12px; color:#555;">
          Outbound today: <strong>{_fmt_price(summary['outbound_today'])}</strong>
          ({_price_delta(summary['outbound_today'], summary['outbound_prev'])})
          &nbsp;&nbsp;|&nbsp;&nbsp;
          Inbound today: <strong>{_fmt_price(summary['inbound_today'])}</strong>
          ({_price_delta(summary['inbound_today'], summary['inbound_prev'])})
          &nbsp;&nbsp;|&nbsp;&nbsp;
          Combo today: <strong>{_fmt_price(summary['combo_today'])}</strong>
          ({_price_delta(summary['combo_today'], summary['combo_prev'])})
        </div>

        <table style="width:100%; border-collapse:collapse; margin-top:10px; font-size:12px;">
          <thead>
            <tr>
              <th style="text-align:left; padding:6px; border-bottom:1px solid #ddd;">Date</th>
              <th style="text-align:right; padding:6px; border-bottom:1px solid #ddd;">Outbound</th>
              <th style="text-align:right; padding:6px; border-bottom:1px solid #ddd;">Inbound</th>
              <th style="text-align:right; padding:6px; border-bottom:1px solid #ddd;">Combo</th>
            </tr>
          </thead>
          <tbody>
    """

    for row in history_rows:
        html += f"""
            <tr>
              <td style="padding:6px; border-bottom:1px solid #f1f1f1;">{row['run_date']}</td>
              <td style="padding:6px; text-align:right; border-bottom:1px solid #f1f1f1;">{_fmt_price(row['best_outbound'])}</td>
              <td style="padding:6px; text-align:right; border-bottom:1px solid #f1f1f1;">{_fmt_price(row['best_inbound'])}</td>
              <td style="padding:6px; text-align:right; border-bottom:1px solid #f1f1f1;">{_fmt_price(row['best_combo'])}</td>
            </tr>
        """

    html += f"""
          </tbody>
        </table>
        <div style="margin-top:8px; font-size:12px; color:#666;">
          Historical min combo: <strong>{_fmt_price(summary['combo_hist_min'])}</strong>
        </div>
      </div>
    """

    return html


def build_html_report(run_date, rows):
    grouped = _group_rows(rows)

    all_outbound_rows = [r for r in rows if r.get("leg_type") == "outbound"]
    all_inbound_rows = [r for r in rows if r.get("leg_type") == "inbound"]

    global_best_outbound = _best_price(all_outbound_rows)
    global_best_inbound = _best_price(all_inbound_rows)

    combo_candidates = []
    for weekend_key in grouped:
        weekend_rows = [
            r for r in rows
            if (r["outbound"], r["inbound"]) == weekend_key
        ]
        out_rows = [r for r in weekend_rows if r.get("leg_type") == "outbound"]
        in_rows = [r for r in weekend_rows if r.get("leg_type") == "inbound"]
        combo = _best_combo_price(out_rows, in_rows)
        if combo is not None:
            combo_candidates.append(combo)

    global_best_combo = min(combo_candidates) if combo_candidates else None

    html = f"""
    <html>
      <body style="font-family: Arial, sans-serif; background:#f5f6f7; color:#222; margin:0; padding:16px;">
        <div style="max-width:980px; margin:0 auto; background:#fff; border:1px solid #ddd;">
          <div style="padding:14px 18px; border-bottom:1px solid #e5e5e5;">
            <div style="font-size:12px; color:#666;">Weekend Flight Bot</div>
            <div style="font-size:21px; font-weight:700; margin-top:4px;">Daily flight report</div>
            <div style="font-size:12px; color:#666; margin-top:4px;">Run date: {run_date.isoformat()}</div>

            <table style="width:100%; border-collapse:collapse; margin-top:12px; font-size:12px;">
              <tr>
                <td style="padding:8px; border:1px solid #eee; background:#fafafa;">
                  <div style="color:#666;">Weekends</div>
                  <div style="font-size:17px; font-weight:700;">{len(grouped)}</div>
                </td>
                <td style="padding:8px; border:1px solid #eee; background:#fafafa;">
                  <div style="color:#666;">Best outbound</div>
                  <div style="font-size:17px; font-weight:700;">{_fmt_price(global_best_outbound)}</div>
                </td>
                <td style="padding:8px; border:1px solid #eee; background:#fafafa;">
                  <div style="color:#666;">Best inbound</div>
                  <div style="font-size:17px; font-weight:700;">{_fmt_price(global_best_inbound)}</div>
                </td>
                <td style="padding:8px; border:1px solid #eee; background:#fafafa;">
                  <div style="color:#666;">Best combo</div>
                  <div style="font-size:17px; font-weight:700;">{_fmt_price(global_best_combo)}</div>
                </td>
              </tr>
            </table>
          </div>
    """

    if not rows:
        html += """
          <div style="padding:20px;">
            <div style="font-size:18px; font-weight:700;">No flights found</div>
          </div>
        """
        html += "</div></body></html>"
        return html

    for weekend_key in sorted(grouped.keys(), key=lambda x: (x[0], x[1])):
        weekend_outbound, weekend_inbound = weekend_key
        weekend_data = grouped[weekend_key]

        outbound_routes = weekend_data["outbound"]
        inbound_routes = weekend_data["inbound"]

        summary = _find_previous_and_history(weekend_outbound, weekend_inbound)

        buying_signal = _trend_label(summary["combo_today"], summary["combo_hist_min"])

        html += f"""
          <div style="margin:14px; border:1px solid #dcdcdc; border-radius:10px; overflow:hidden;">
            <div style="padding:14px 16px; background:#fafafa; border-bottom:1px solid #ececec;">
              <div style="font-size:18px; font-weight:700;">
                {_day_label(weekend_outbound)} → {_day_label(weekend_inbound)}
              </div>
              <div style="margin-top:6px; font-size:12px; color:#444;">
                Combo today: <strong>{_fmt_price(summary['combo_today'])}</strong>
                &nbsp;&nbsp;|&nbsp;&nbsp;
                Hist. min: <strong>{_fmt_price(summary['combo_hist_min'])}</strong>
                &nbsp;&nbsp;|&nbsp;&nbsp;
                Signal: <strong>{buying_signal}</strong>
              </div>
            </div>

            <table style="width:100%; border-collapse:collapse; table-layout:fixed;">
              <tr>
                {_build_leg_column("Outbound", _day_label(weekend_outbound), outbound_routes)}
                {_build_leg_column("Inbound", _day_label(weekend_inbound), inbound_routes)}
              </tr>
            </table>

            {_build_history_table(summary)}
          </div>
        """

    html += """
        </div>
      </body>
    </html>
    """

    return html
