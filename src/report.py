from __future__ import annotations

import calendar
from collections import defaultdict
from datetime import date, timedelta

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

MONTH_LABELS = {
    1: "January",
    2: "February",
    3: "March",
    4: "April",
    5: "May",
    6: "June",
    7: "July",
    8: "August",
    9: "September",
    10: "October",
    11: "November",
    12: "December",
}


def _weekday_short(d: date) -> str:
    return WEEKDAY_LABELS[d.weekday()]


def _fmt_day(d: date) -> str:
    return f"{_weekday_short(d)} {d.isoformat()}"


def _fmt_price(value: float | None) -> str:
    return "—" if value is None else f"{value:.2f} EUR"


def _fmt_price_compact(value: float | None) -> str:
    return "—" if value is None else f"{value:.0f} €"


def _price_delta(current: float | None, previous: float | None) -> str:
    if current is None:
        return "—"
    if previous is None:
        return "new"

    diff = round(current - previous, 2)
    if diff == 0:
        return "0.00"
    if diff > 0:
        return f"+{diff:.2f}"
    return f"{diff:.2f}"


def _delta_color(delta: str) -> str:
    if delta == "new":
        return "#1d4ed8"
    if delta.startswith("+"):
        return "#b42318"
    if delta.startswith("-"):
        return "#027a48"
    return "#666"


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


def _best_price(rows: list[dict]) -> float | None:
    if not rows:
        return None
    return min(row["price"] for row in rows)


def _best_combo_price(outbound_rows: list[dict], inbound_rows: list[dict]) -> float | None:
    out_best = _best_price(outbound_rows)
    in_best = _best_price(inbound_rows)

    if out_best is None or in_best is None:
        return None

    return out_best + in_best


def _find_previous_and_history(
    weekend_outbound: date,
    weekend_inbound: date,
) -> dict[str, float | None | list[dict]]:
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
        "history_rows": history[-6:],
    }


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


def _flatten_leg_groups(route_groups: dict[str, list[dict]]) -> list[dict]:
    rows: list[dict] = []
    for route_key in sorted(route_groups.keys()):
        rows.extend(route_groups[route_key])
    rows.sort(key=lambda r: (r["price"], r.get("outbound_departure", "99:99")))
    return rows


def _build_option_line(item: dict) -> str:
    return (
        f"{item.get('origin', '')}→{item.get('destination', '')} | "
        f"{item.get('airline', 'Unknown')} | "
        f"{item.get('outbound_departure', 'N/A')}-{item.get('outbound_arrival', 'N/A')}"
        f" | {_fmt_price_compact(item.get('price'))}"
    )


def _build_leg_compact_section(title: str, day_label: str, route_groups: dict[str, list[dict]]) -> str:
    html = f"""
      <div style="padding:12px 14px;">
        <div style="font-size:15px; font-weight:700; color:#111;">{title}</div>
        <div style="margin-top:2px; font-size:12px; color:#666;">{day_label}</div>
    """

    if not route_groups:
        html += """
        <div style="margin-top:10px; font-size:12px; color:#999;">No options found.</div>
        """
        html += "</div>"
        return html

    for route_key in sorted(route_groups.keys()):
        rows = route_groups[route_key]
        best = rows[0]["price"] if rows else None

        html += f"""
        <div style="margin-top:10px; border:1px solid #ececec; border-radius:8px; overflow:hidden;">
          <div style="padding:8px 10px; background:#fafafa; border-bottom:1px solid #ececec;">
            <span style="font-size:13px; font-weight:700;">{route_key}</span>
            <span style="float:right; font-size:13px; font-weight:700;">{_fmt_price_compact(best)}</span>
          </div>
          <div style="padding:8px 10px;">
        """

        for idx, item in enumerate(rows[:3], start=1):
            html += f"""
            <div style="font-size:12px; line-height:1.45; color:#333; margin-bottom:6px;">
              {idx}) {_build_option_line(item)}
            </div>
            """

        html += """
          </div>
        </div>
        """

    html += "</div>"
    return html


def _build_history_summary_block(summary: dict) -> str:
    combo_today = summary["combo_today"]
    combo_prev = summary["combo_prev"]
    combo_hist_min = summary["combo_hist_min"]
    signal = _trend_label(combo_today, combo_hist_min)
    delta = _price_delta(combo_today, combo_prev)
    color = _delta_color(delta)

    return f"""
      <div style="padding:10px 14px; border-top:1px solid #ececec; background:#fcfcfc;">
        <div style="font-size:12px; color:#444;">
          Combo today: <strong>{_fmt_price(combo_today)}</strong>
          &nbsp;&nbsp;|&nbsp;&nbsp;
          vs prev: <strong style="color:{color};">{delta}</strong>
          &nbsp;&nbsp;|&nbsp;&nbsp;
          Hist. min: <strong>{_fmt_price(combo_hist_min)}</strong>
          &nbsp;&nbsp;|&nbsp;&nbsp;
          Signal: <strong>{signal}</strong>
        </div>
      </div>
    """


def _build_history_table(summary: dict) -> str:
    history_rows = summary.get("history_rows", [])
    if not history_rows:
        return """
          <div style="padding:10px 14px; border-top:1px solid #ececec;">
            <div style="font-size:12px; color:#888;">No historical data yet.</div>
          </div>
        """

    html = """
      <div style="padding:10px 14px; border-top:1px solid #ececec;">
        <div style="font-size:13px; font-weight:700; margin-bottom:8px;">Recent history</div>
        <table style="width:100%; border-collapse:collapse; font-size:12px;">
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
              <td style="padding:6px; text-align:right; border-bottom:1px solid #f1f1f1;">{_fmt_price_compact(row['best_outbound'])}</td>
              <td style="padding:6px; text-align:right; border-bottom:1px solid #f1f1f1;">{_fmt_price_compact(row['best_inbound'])}</td>
              <td style="padding:6px; text-align:right; border-bottom:1px solid #f1f1f1;">{_fmt_price_compact(row['best_combo'])}</td>
            </tr>
        """

    html += """
          </tbody>
        </table>
      </div>
    """
    return html


def _nato_holidays() -> set[date]:
    holidays = {
        date(2026, 4, 3),
        date(2026, 4, 6),
        date(2026, 4, 27),
        date(2026, 5, 1),
        date(2026, 5, 5),
        date(2026, 5, 14),
        date(2026, 5, 25),
        date(2026, 11, 2),
    }

    current = date(2026, 12, 23)
    end = date(2027, 1, 1)
    while current <= end:
        holidays.add(current)
        current += timedelta(days=1)

    return holidays


def _months_in_scope(grouped: dict[tuple[date, date], dict]) -> list[tuple[int, int]]:
    months = set()

    for weekend_outbound, weekend_inbound in grouped.keys():
        months.add((weekend_outbound.year, weekend_outbound.month))
        months.add((weekend_inbound.year, weekend_inbound.month))

    return sorted(months)


def _day_style(day: date, outbound_days: set[date], inbound_days: set[date], holidays: set[date]) -> str:
    is_out = day in outbound_days
    is_in = day in inbound_days
    is_holiday = day in holidays

    bg = "#ffffff"
    color = "#222"
    border = "1px solid #eee"

    if is_out and is_in and is_holiday:
        bg = "#d8b4fe"
        border = "1px solid #a855f7"
    elif is_out and is_in:
        bg = "#c7d2fe"
        border = "1px solid #6366f1"
    elif is_out and is_holiday:
        bg = "#bfdbfe"
        border = "1px solid #2563eb"
    elif is_in and is_holiday:
        bg = "#bbf7d0"
        border = "1px solid #16a34a"
    elif is_out:
        bg = "#dbeafe"
        border = "1px solid #60a5fa"
    elif is_in:
        bg = "#dcfce7"
        border = "1px solid #4ade80"
    elif is_holiday:
        bg = "#fee2e2"
        border = "1px solid #f87171"

    return f"background:{bg}; color:{color}; border:{border};"


def _build_month_calendar(
    year: int,
    month: int,
    outbound_days: set[date],
    inbound_days: set[date],
    holidays: set[date],
) -> str:
    cal = calendar.Calendar(firstweekday=0)
    weeks = cal.monthdatescalendar(year, month)

    html = f"""
      <div style="border:1px solid #ddd; border-radius:10px; overflow:hidden; background:#fff;">
        <div style="padding:10px 12px; background:#fafafa; border-bottom:1px solid #ececec; font-size:15px; font-weight:700;">
          {MONTH_LABELS[month]} {year}
        </div>
        <table style="width:100%; border-collapse:collapse; table-layout:fixed; font-size:11px;">
          <thead>
            <tr>
              <th style="padding:6px; border-bottom:1px solid #eee; color:#666;">Mon</th>
              <th style="padding:6px; border-bottom:1px solid #eee; color:#666;">Tue</th>
              <th style="padding:6px; border-bottom:1px solid #eee; color:#666;">Wed</th>
              <th style="padding:6px; border-bottom:1px solid #eee; color:#666;">Thu</th>
              <th style="padding:6px; border-bottom:1px solid #eee; color:#666;">Fri</th>
              <th style="padding:6px; border-bottom:1px solid #eee; color:#666;">Sat</th>
              <th style="padding:6px; border-bottom:1px solid #eee; color:#666;">Sun</th>
            </tr>
          </thead>
          <tbody>
    """

    for week in weeks:
        html += "<tr>"
        for day in week:
            in_month = day.month == month
            style = _day_style(day, outbound_days, inbound_days, holidays) if in_month else "background:#f8f8f8; color:#bbb; border:1px solid #f0f0f0;"
            html += f"""
              <td style="height:34px; text-align:center; vertical-align:middle; {style}">
                {day.day if in_month else ""}
              </td>
            """
        html += "</tr>"

    html += """
          </tbody>
        </table>
      </div>
    """
    return html


def _build_calendar_section(grouped: dict[tuple[date, date], dict]) -> str:
    outbound_days = {weekend_outbound for weekend_outbound, _ in grouped.keys()}
    inbound_days = {weekend_inbound for _, weekend_inbound in grouped.keys()}
    holidays = _nato_holidays()
    months = _months_in_scope(grouped)

    if not months:
        return ""

    html = """
      <div style="padding:14px 16px; border-bottom:1px solid #e5e5e5;">
        <div style="font-size:16px; font-weight:700;">Calendar view</div>
        <div style="margin-top:8px; display:flex; gap:10px; flex-wrap:wrap; font-size:12px; color:#444;">
          <div><span style="display:inline-block; width:12px; height:12px; background:#dbeafe; border:1px solid #60a5fa; vertical-align:middle;"></span> Outbound</div>
          <div><span style="display:inline-block; width:12px; height:12px; background:#dcfce7; border:1px solid #4ade80; vertical-align:middle;"></span> Inbound</div>
          <div><span style="display:inline-block; width:12px; height:12px; background:#fee2e2; border:1px solid #f87171; vertical-align:middle;"></span> NATO holiday</div>
          <div><span style="display:inline-block; width:12px; height:12px; background:#d8b4fe; border:1px solid #a855f7; vertical-align:middle;"></span> Flight + holiday overlap</div>
        </div>
        <div style="margin-top:12px; display:grid; grid-template-columns:repeat(auto-fit, minmax(280px, 1fr)); gap:12px;">
    """

    for year, month in months:
        html += _build_month_calendar(
            year=year,
            month=month,
            outbound_days=outbound_days,
            inbound_days=inbound_days,
            holidays=holidays,
        )

    html += """
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
        weekend_rows = [r for r in rows if (r["outbound"], r["inbound"]) == weekend_key]
        out_rows = [r for r in weekend_rows if r.get("leg_type") == "outbound"]
        in_rows = [r for r in weekend_rows if r.get("leg_type") == "inbound"]
        combo = _best_combo_price(out_rows, in_rows)
        if combo is not None:
            combo_candidates.append(combo)

    global_best_combo = min(combo_candidates) if combo_candidates else None

    html = f"""
    <html>
      <body style="font-family: Arial, sans-serif; background:#f5f6f7; color:#222; margin:0; padding:14px;">
        <div style="max-width:980px; margin:0 auto; background:#fff; border:1px solid #ddd;">
          <div style="padding:14px 16px; border-bottom:1px solid #e5e5e5;">
            <div style="font-size:12px; color:#666;">Weekend Flight Bot</div>
            <div style="font-size:22px; font-weight:700; margin-top:4px;">Daily flight report</div>
            <div style="font-size:12px; color:#666; margin-top:4px;">Run date: {run_date.isoformat()}</div>

            <div style="margin-top:12px; display:grid; grid-template-columns:repeat(4,1fr); gap:8px;">
              <div style="padding:10px; border:1px solid #eee; background:#fafafa;">
                <div style="font-size:11px; color:#666;">Weekends</div>
                <div style="font-size:18px; font-weight:700;">{len(grouped)}</div>
              </div>
              <div style="padding:10px; border:1px solid #eee; background:#fafafa;">
                <div style="font-size:11px; color:#666;">Best outbound</div>
                <div style="font-size:18px; font-weight:700;">{_fmt_price_compact(global_best_outbound)}</div>
              </div>
              <div style="padding:10px; border:1px solid #eee; background:#fafafa;">
                <div style="font-size:11px; color:#666;">Best inbound</div>
                <div style="font-size:18px; font-weight:700;">{_fmt_price_compact(global_best_inbound)}</div>
              </div>
              <div style="padding:10px; border:1px solid #eee; background:#fafafa;">
                <div style="font-size:11px; color:#666;">Best combo</div>
                <div style="font-size:18px; font-weight:700;">{_fmt_price_compact(global_best_combo)}</div>
              </div>
            </div>
          </div>

          {_build_calendar_section(grouped)}
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
        outbound_flat = _flatten_leg_groups(outbound_routes)
        inbound_flat = _flatten_leg_groups(inbound_routes)

        best_out = _best_price(outbound_flat)
        best_in = _best_price(inbound_flat)
        best_combo = _best_combo_price(outbound_flat, inbound_flat)

        combo_delta = _price_delta(best_combo, summary["combo_prev"])
        combo_delta_color = _delta_color(combo_delta)

        html += f"""
          <div style="margin:12px; border:1px solid #dcdcdc; border-radius:10px; overflow:hidden;">
            <div style="padding:12px 14px; background:#fafafa; border-bottom:1px solid #ececec;">
              <div style="font-size:18px; font-weight:700;">
                Weekend starting {weekend_outbound.isoformat()} ({_fmt_day(weekend_outbound)} → {_fmt_day(weekend_inbound)})
              </div>
              <div style="margin-top:8px; display:flex; gap:18px; flex-wrap:wrap; font-size:13px;">
                <div>Best outbound: <strong>{_fmt_price(best_out)}</strong></div>
                <div>Best inbound: <strong>{_fmt_price(best_in)}</strong></div>
                <div>Best manual combo: <strong>{_fmt_price(best_combo)}</strong></div>
                <div>Δ prev: <strong style="color:{combo_delta_color};">{combo_delta}</strong></div>
              </div>
            </div>

            <table style="width:100%; border-collapse:collapse; table-layout:fixed;">
              <tr>
                <td style="width:50%; vertical-align:top; border-right:1px solid #eee;">
                  {_build_leg_compact_section("Outbound", _fmt_day(weekend_outbound), outbound_routes)}
                </td>
                <td style="width:50%; vertical-align:top;">
                  {_build_leg_compact_section("Inbound", _fmt_day(weekend_inbound), inbound_routes)}
                </td>
              </tr>
            </table>

            {_build_history_summary_block(summary)}
            {_build_history_table(summary)}
          </div>
        """

    html += """
        </div>
      </body>
    </html>
    """

    return html
