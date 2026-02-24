from __future__ import annotations

import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import date, timedelta


def _html_escape(s: str) -> str:
    return (s.replace("&", "&amp;")
             .replace("<", "&lt;")
             .replace(">", "&gt;")
             .replace('"', "&quot;"))


def build_html_report(all_origins: dict[str, dict]) -> str:
    """
    all_origins:
      origin_label -> weekend_buckets
      weekend_buckets: weekend_start -> pattern -> list[FlightLine]
    """
    # collect all weekend starts
    weekend_starts = sorted({ws for buckets in all_origins.values() for ws in buckets.keys()})

    def weekend_range(ws):
        # Thu->Mon range shown in screenshot
        return ws, ws + timedelta(days=4)

    css = """
    <style>
      body { font-family: -apple-system, Segoe UI, Roboto, Arial, sans-serif; color:#111; }
      .week { padding: 12px 0; border-top: 1px solid #eee; }
      .title { font-size: 16px; font-weight: 700; margin: 0 0 8px; }
      .sub { font-size: 13px; color:#444; margin: 0 0 10px; }
      .best { background:#f6f8fa; padding:10px; border-radius:10px; margin: 8px 0 12px; }
      .pill { display:inline-block; padding:4px 10px; border-radius:999px; background:#e7f3ff; color:#0b63ce; font-weight:700; font-size:12px; }
      .card { border:1px solid #eee; border-radius:12px; padding:10px 12px; margin:10px 0; }
      .card h4 { margin:0 0 6px; font-size: 13px; color:#333; }
      .price { font-size: 20px; font-weight: 800; margin: 2px 0 8px; }
      .line { font-size: 13px; color:#222; margin: 3px 0; }
      .muted { color:#666; }
      .origin { font-weight:700; }
    </style>
    """

    html = [f"<html><head>{css}</head><body>"]
    html.append(f"<h2>Weekend flights monitor — {date.today().isoformat()}</h2>")

    # per weekend
    for ws in weekend_starts:
        start, end = weekend_range(ws)
        html.append('<div class="week">')
        html.append(f'<p class="title">Weekend starting {start.isoformat()} (~ {start.isoformat()} → {end.isoformat()})</p>')

        # compute best across origins/patterns
        best_price = None
        best_ccy = "EUR"
        for origin, buckets in all_origins.items():
            patterns = buckets.get(ws, {})
            for p, lines in patterns.items():
                if not lines:
                    continue
                if best_price is None or lines[0].price < best_price:
                    best_price = lines[0].price
                    best_ccy = lines[0].currency

        html.append('<div class="best">')
        if best_price is None:
            html.append('<div class="sub"><b>Best in this weekend:</b> NONE (no results after 17:00)</div>')
        else:
            html.append(f'<div class="sub"><b>Best in this weekend:</b> {best_price:.2f} {best_ccy}</div>')
        html.append('</div>')

        # show per origin sections, then patterns (to match “like screenshot”, you can reorder later)
        for origin, buckets in all_origins.items():
            patterns = buckets.get(ws, {})
            if not patterns:
                continue
            html.append(f'<div class="sub"><span class="origin">{_html_escape(origin)}</span></div>')

            for pattern_label in ["Fri → Sun", "Fri → Mon", "Thu → Sun", "Thu → Mon"]:
                lines = patterns.get(pattern_label, [])
                if not lines:
                    continue

                html.append('<div class="card">')
                html.append(f'<h4>{_html_escape(pattern_label)} ({ws.isoformat()} → {(ws + timedelta(days=2 if "Sun" in pattern_label else 4)).isoformat()})</h4>')
                html.append(f'<div class="price">{lines[0].price:.2f} {lines[0].currency}</div>')

                for idx, ln in enumerate(lines[:3], start=1):
                    carrier = ln.carrier_code or ""
                    flight = ln.flight_no or ""
                    html.append(f'<div class="line">{idx}) {ln.price:.2f} {ln.currency} <span class="muted">{carrier}</span> OUT {flight} {ln.out_time} | IN {ln.in_time}</div>')

                html.append('</div>')

        html.append('</div>')

    html.append("</body></html>")
    return "".join(html)


def send_email(subject: str, html_body: str) -> None:
    smtp_host = os.environ["SMTP_HOST"]
    smtp_port = int(os.environ.get("SMTP_PORT", "587"))
    smtp_user = os.environ["SMTP_USER"]
    smtp_pass = os.environ["SMTP_PASS"]
    email_to = os.environ["EMAIL_TO"]

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = smtp_user
    msg["To"] = email_to

    msg.attach(MIMEText(html_body, "html", "utf-8"))

    with smtplib.SMTP(smtp_host, smtp_port) as server:
        server.starttls()
        server.login(smtp_user, smtp_pass)
        server.sendmail(smtp_user, [email_to], msg.as_string())
