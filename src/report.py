from __future__ import annotations

from collections import defaultdict
from datetime import date


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


def _price_delta(current: float, previous: float | None) -> str:
    if previous is None:
        return "new"

    diff = round(current - previous, 2)
    if diff == 0:
        return "0.00 €"
    if diff > 0:
        return f"+{diff:.2f} €"
    return f"{diff:.2f} €"


def _trend_label(current: float, historical_min: float | None) -> str:
    if historical_min is None:
        return "Too early to tell"

    if historical_min <= 0:
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
    outbound_best = _best_price(outbound_rows)
    inbound_best = _best_price(inbound_rows)

    if outbound_best is None or inbound_best is None:
        return None

    return outbound_best + inbound_best


def _find_previous_and_history(
    all_rows: list[dict],
    weekend_key: tuple[date, date],
) -> dict[str, float | None]:
    """
    Placeholder-compatible historical summary.

    With the current pipeline, we only have today's rows in the report layer.
    This function is written so the email already supports history labels.
    When historical retrieval is added, only this function will need upgrading.
    """

    weekend_rows = [
        row for row in all_rows
        if (row["outbound"], row["inbound"]) == weekend_key
    ]

    outbound_rows = [r for r in weekend_rows if r.get("leg_type") == "outbound"]
    inbound_rows = [r for r in weekend_rows if r.get("leg_type") == "inbound"]

    outbound_best = _best_price(outbound_rows)
    inbound_best = _best_price(inbound_rows)
    combo_best = _best_combo_price(outbound_rows, inbound_rows)

    return {
        "outbound_today": outbound_best,
        "inbound_today": inbound_best,
        "combo_today": combo_best,
        "outbound_prev": None,
        "inbound_prev": None,
        "combo_prev": None,
        "outbound_hist_min": outbound_best,
        "inbound_hist_min": inbound_best,
        "combo_hist_min": combo_best,
    }


def _build_route_table(rows: list[dict], route_title: str) -> str:
    if not rows:
        return f"""
          <div style="padding:10px 0 14px 0;">
            <div style="font-size:14px; color:#666;">{route_title}</div>
            <div style="margin-top:6px; font-size:13px; color:#888;">No options found.</div>
          </div>
        """

    html = f"""
      <div style="padding:10px 0 14px 0;">
        <div style="font-size:14px; font-weight:700; color:#222;">{route_title}</div>
    """

    for idx, item in enumerate(rows, start=1):
        html += f"""
          <div style="margin-top:10px; padding:10px 12px; border:1px solid #e6e6e6; border-radius:8px; background:#fff;">
            <div style="font-size:14px; font-weight:700;">
              {idx}) {item.get('airline', 'Unknown')} — {item['price']:.2f} EUR
            </div>
            <div style="margin-top:4px; font-size:13px; color:#333;">
              DEP {item.get('outbound_departure', 'N/A')} | ARR {item.get('outbound_arrival', 'N/A')}
            </div>
            <div style="margin-top:4px; font-size:12px; color:#666;">
              Flight no: {item.get('outbound_flight_no', 'N/A')}
            </div>
            <div style="margin-top:6px; font-size:12px;">
              <a href="{item.get('source_url', '#')}">Open result</a>
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
      <td style="width:50%; vertical-align:top; padding:14px; border-left:1px solid #eee;">
        <div style="font-size:18px; font-weight:700; color:#111;">{title}</div>
        <div style="margin-top:4px; font-size:13px; color:#666;">{day_label}</div>
    """

    if not grouped_routes:
        html += """
        <div style="margin-top:14px; font-size:13px; color:#888;">No options found.</div>
        """
    else:
        for route_key in sorted(grouped_routes.keys()):
            html += _build_route_table(grouped_routes[route_key], route_key)

    html += "</td>"
    return html


def _build_history_table(summary: dict[str, float | None]) -> str:
    outbound_today = summary["outbound_today"]
    inbound_today = summary["inbound_today"]
    combo_today = summary["combo_today"]

    outbound_prev = summary["outbound_prev"]
    inbound_prev = summary["inbound_prev"]
    combo_prev = summary["combo_prev"]

    outbound_hist_min = summary["outbound_hist_min"]
    inbound_hist_min = summary["inbound_hist_min"]
    combo_hist_min = summary["combo_hist_min"]

    def fmt(value: float | None) -> str:
        return "—" if value is None else f"{value:.2f} €"

    return f"""
      <div style="padding:16px 20px; border-top:1px solid #ececec;">
        <div style="font-size:16px; font-weight:700;">Trend summary</div>
        <table style="width:100%; border-collapse:collapse; margin-top:10px; font-size:13px;">
          <thead>
            <tr>
              <th style="text-align:left; padding:8px; border-bottom:1px solid #ddd;">Metric</th>
              <th style="text-align:right; padding:8px; border-bottom:1px solid #ddd;">Today</th>
              <th style="text-align:right; padding:8px; border-bottom:1px solid #ddd;">vs prev</th>
              <th style="text-align:right; padding:8px; border-bottom:1px solid #ddd;">Hist. min</th>
            </tr>
          </thead>
          <tbody>
            <tr>
              <td style="padding:8px; border-bottom:1px solid #f0f0f0;">Best outbound</td>
              <td style="padding:8px; text-align:right; border-bottom:1px solid #f0f0f0;">{fmt(outbound_today)}</td>
              <td style="padding:8px; text-align:right; border-bottom:1px solid #f0f0f0;">{_price_delta(outbound_today, outbound_prev) if outbound_today is not None else '—'}</td>
              <td style="padding:8px; text-align:right; border-bottom:1px solid #f0f0f0;">{fmt(outbound_hist_min)}</td>
            </tr>
            <tr>
              <td style="padding:8px; border-bottom:1px solid #f0f0f0;">Best inbound</td>
              <td style="padding:8px; text-align:right; border-bottom:1px solid #f0f0f0;">{fmt(inbound_today)}</td>
              <td style="padding:8px; text-align:right; border-bottom:1px solid #f0f0f0;">{_price_delta(inbound_today, inbound_prev) if inbound_today is not None else '—'}</td>
              <td style="padding:8px; text-align:right; border-bottom:1px solid #f0f0f0;">{fmt(inbound_hist_min)}</td>
            </tr>
            <tr>
              <td style="padding:8px;">Best manual combo</td>
              <td style="padding:8px; text-align:right;">{fmt(combo_today)}</td>
              <td style="padding:8px; text-align:right;">{_price_delta(combo_today, combo_prev) if combo_today is not None else '—'}</td>
              <td style="padding:8px; text-align:right;">{fmt(combo_hist_min)}</td>
            </tr>
          </tbody>
        </table>
      </div>
    """


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

    def fmt(value: float | None) -> str:
        return "—" if value is None else f"{value:.2f} €"

    html = f"""
    <html>
      <body style="font-family: Arial, sans-serif; background:#f5f6f7; color:#222; margin:0; padding:20px;">
        <div style="max-width:1040px; margin:0 auto; background:#fff; border:1px solid #ddd;">
          <div style="padding:16px 20px; border-bottom:1px solid #e5e5e5;">
            <div style="font-size:12px; color:#666;">Weekend Flight Bot</div>
            <div style="font-size:22px; font-weight:700; margin-top:4px;">Daily flight report</div>
            <div style="font-size:13px; color:#666; margin-top:6px;">Run date: {run_date.isoformat()}</div>

            <table style="width:100%; border-collapse:collapse; margin-top:14px; font-size:13px;">
              <tr>
                <td style="padding:10px; border:1px solid #eee; background:#fafafa;">
                  <div style="color:#666;">Weekends analyzed</div>
                  <div style="font-size:18px; font-weight:700;">{len(grouped)}</div>
                </td>
                <td style="padding:10px; border:1px solid #eee; background:#fafafa;">
                  <div style="color:#666;">Best outbound found</div>
                  <div style="font-size:18px; font-weight:700;">{fmt(global_best_outbound)}</div>
                </td>
                <td style="padding:10px; border:1px solid #eee; background:#fafafa;">
                  <div style="color:#666;">Best inbound found</div>
                  <div style="font-size:18px; font-weight:700;">{fmt(global_best_inbound)}</div>
                </td>
                <td style="padding:10px; border:1px solid #eee; background:#fafafa;">
                  <div style="color:#666;">Best manual combo</div>
                  <div style="font-size:18px; font-weight:700;">{fmt(global_best_combo)}</div>
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

        weekend_rows = [
            r for r in rows
            if (r["outbound"], r["inbound"]) == weekend_key
        ]

        outbound_rows = [r for r in weekend_rows if r.get("leg_type") == "outbound"]
        inbound_rows = [r for r in weekend_rows if r.get("leg_type") == "inbound"]

        summary = _find_previous_and_history(rows, weekend_key)

        buying_signal = _trend_label(
            summary["combo_today"] if summary["combo_today"] is not None else 0,
            summary["combo_hist_min"],
        )

        html += f"""
          <div style="border-top:2px solid #d8d8d8;">
            <div style="padding:18px 20px; background:#fafafa;">
              <div style="font-size:22px; font-weight:700;">
                Weekend: {_day_label(weekend_outbound)} → {_day_label(weekend_inbound)}
              </div>
              <div style="margin-top:8px; font-size:14px; color:#444;">
                Best manual combo today: <strong>{fmt(summary['combo_today'])}</strong>
                &nbsp;&nbsp;|&nbsp;&nbsp;
                Historical min combo: <strong>{fmt(summary['combo_hist_min'])}</strong>
                &nbsp;&nbsp;|&nbsp;&nbsp;
                Buying signal: <strong>{buying_signal}</strong>
              </div>
            </div>

            <div style="padding:0 20px 18px 20px;">
              <table style="width:100%; border-collapse:collapse; table-layout:fixed; margin-top:16px; border:1px solid #eee;">
                <tr>
                  {_build_leg_column("Outbound options", _day_label(weekend_outbound), outbound_routes)}
                  {_build_leg_column("Inbound options", _day_label(weekend_inbound), inbound_routes)}
                </tr>
              </table>
            </div>

            {_build_history_table(summary)}
          </div>
        """

    html += """
        </div>
      </body>
    </html>
    """

    return html
