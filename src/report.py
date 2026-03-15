from __future__ import annotations

from collections import defaultdict
from datetime import date
from html import escape

from src.models import FlightOption
from src.store import previous_best_price


def _format_delta(current: float, previous: float | None) -> str:
    if previous is None:
        return "NEW"

    diff = round(current - previous, 2)
    if diff == 0:
        return "0.00"
    if diff > 0:
        return f"+{diff:.2f}"
    return f"{diff:.2f}"


def _group_options(options: list[FlightOption]) -> dict[date, dict[str, list[FlightOption]]]:
    grouped: dict[date, dict[str, list[FlightOption]]] = defaultdict(lambda: defaultdict(list))
    for opt in options:
        grouped[opt.outbound_date][opt.pattern_label].append(opt)

    for weekend_start in grouped:
        for pattern in grouped[weekend_start]:
            grouped[weekend_start][pattern] = sorted(
                grouped[weekend_start][pattern],
                key=lambda x: x.total_price_eur,
            )[:3]

    return dict(grouped)


def build_html_report(run_date: date, options: list[FlightOption]) -> str:
    grouped = _group_options(options)

    parts: list[str] = []
    parts.append(
        """
        <html>
        <body style="font-family: Arial, sans-serif; background:#f5f6f7; color:#222; margin:0; padding:20px;">
          <div style="max-width:860px; margin:0 auto; background:#ffffff; border:1px solid #ddd;">
        """
    )
    parts.append(
        f"""
        <div style="padding:16px 20px; border-bottom:1px solid #e5e5e5;">
          <div style="font-size:12px; color:#666;">Weekend Flight Bot</div>
          <div style="font-size:22px; font-weight:700; margin-top:4px;">Daily flight report</div>
          <div style="font-size:13px; color:#666; margin-top:6px;">Run date: {escape(run_date.isoformat())}</div>
        </div>
        """
    )

    if not grouped:
        parts.append(
            """
            <div style="padding:20px;">
              <div style="font-size:16px; font-weight:700;">No matching flights found</div>
            </div>
            """
        )
    else:
        for weekend_start in sorted(grouped.keys()):
            weekend_patterns = grouped[weekend_start]
            weekend_best = min(
                opt.total_price_eur
                for pattern_options in weekend_patterns.values()
                for opt in pattern_options
            )

            parts.append(
                f"""
                <div style="padding:18px 20px; border-top:1px solid #ececec; background:#fafafa;">
                  <div style="font-size:18px; font-weight:700;">
                    Weekend starting {escape(weekend_start.isoformat())}
                  </div>
                  <div style="margin-top:6px; font-size:14px; color:#444;">
                    Best in this weekend: <strong>{weekend_best:.2f} EUR</strong>
                  </div>
                </div>
                """
            )

            for pattern_label in sorted(weekend_patterns.keys()):
                top_options = weekend_patterns[pattern_label]
                best = top_options[0]
                prev = previous_best_price(run_date, weekend_start, pattern_label)
                delta = _format_delta(best.total_price_eur, prev)

                delta_color = "#666"
                if delta.startswith("+"):
                    delta_color = "#b42318"
                elif delta.startswith("-"):
                    delta_color = "#027a48"
                elif delta == "NEW":
                    delta_color = "#1d4ed8"

                parts.append(
                    f"""
                    <div style="padding:16px 20px; border-top:1px solid #f0f0f0;">
                      <div style="font-size:14px; color:#666;">{escape(pattern_label)} ({best.outbound_date.isoformat()} -> {best.inbound_date.isoformat()})</div>
                      <div style="margin-top:6px; display:flex; gap:12px; align-items:baseline;">
                        <span style="font-size:28px; font-weight:700;">{best.total_price_eur:.2f} EUR</span>
                        <span style="font-size:14px; font-weight:700; color:{delta_color};">{escape(delta)}</span>
                      </div>
                    """
                )

                for idx, opt in enumerate(top_options, start=1):
                    parts.append(
                        f"""
                        <div style="margin-top:10px; font-size:13px; color:#333;">
                          {idx}) <strong>{opt.total_price_eur:.2f} EUR</strong>
                          &nbsp; {escape(opt.airline)}
                          &nbsp; OUT {escape(opt.outbound_flight_no)} {escape(opt.outbound_departure)}-{escape(opt.outbound_arrival)}
                          &nbsp; IN {escape(opt.inbound_flight_no)} {escape(opt.inbound_departure)}-{escape(opt.inbound_arrival)}
                        </div>
                        """
                    )

                parts.append("</div>")

    parts.append(
        """
          </div>
        </body>
        </html>
        """
    )
    return "".join(parts)
