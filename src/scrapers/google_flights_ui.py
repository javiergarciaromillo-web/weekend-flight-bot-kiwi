from __future__ import annotations

import re
from pathlib import Path
from typing import List, Tuple
from datetime import date, datetime

from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError


DEBUG_DIR = Path("debug")


def _safe_name(text: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_.-]+", "_", text)


def _build_google_flights_url(origin: str, destination: str, leg_date: str) -> str:
    return (
        "https://www.google.com/travel/flights/search"
        f"?hl=en&curr=EUR"
        f"&q=Flights%20from%20{origin}%20to%20{destination}%20on%20{leg_date}%20one%20way"
    )


def _click_if_present(page, selectors: list[str], timeout: int = 2500) -> bool:
    for selector in selectors:
        try:
            locator = page.locator(selector).first
            if locator.is_visible(timeout=timeout):
                locator.click(timeout=timeout)
                return True
        except Exception:
            pass
    return False


def _maybe_handle_google_interstitials(page) -> None:
    _click_if_present(
        page,
        [
            "button:has-text('Accept all')",
            "button:has-text('I agree')",
            "button:has-text('Aceptar todo')",
            "button:has-text('Acepto')",
            "button:has-text('Reject all')",
            "button:has-text('No thanks')",
            "button:has-text('Ahora no')",
            "button:has-text('Not now')",
            "text='Proceed anyway'",
            "text='Continue anyway'",
        ],
        timeout=3000,
    )


def _collect_page_text(page) -> str:
    try:
        return page.inner_text("body")
    except Exception:
        return ""


def _normalize_text(text: str) -> str:
    return (
        text.replace("\u202f", " ")
        .replace("\xa0", " ")
        .replace("–", "-")
        .replace("—", "-")
    )


def _parse_time_to_24h(value: str) -> datetime.time | None:
    value = value.strip().upper().replace("\u202f", " ").replace("\xa0", " ")
    value = value.replace("+1", "").strip()

    for fmt in ("%I:%M %p", "%H:%M"):
        try:
            return datetime.strptime(value, fmt).time()
        except ValueError:
            pass

    return None


def _departure_ok(leg_date: date, departure_time: str) -> bool:
    """
    Rules:
    - Thursday outbound -> from 16:00
    - Friday outbound -> whole day
    - Sunday inbound -> from 16:00
    - Monday inbound -> whole day
    """
    weekday = leg_date.weekday()

    if weekday in (4, 0):  # Friday or Monday
        return True

    dep = _parse_time_to_24h(departure_time)
    if dep is None:
        return False

    threshold = datetime.strptime("16:00", "%H:%M").time()
    return dep >= threshold


def _canonical_airline_name(raw: str) -> str:
    raw_lower = raw.lower()

    if "vueling" in raw_lower:
        return "Vueling"
    if "transavia" in raw_lower:
        return "Transavia"
    if "klm" in raw_lower:
        return "KLM"
    if "british airways" in raw_lower:
        return "British Airways"
    if "swiss" in raw_lower:
        return "SWISS"

    return raw.strip()


def _is_time_line(text: str) -> bool:
    return re.fullmatch(r"\d{1,2}:\d{2}\s?(?:AM|PM)(?:\+1)?", text.strip(), flags=re.IGNORECASE) is not None


def _is_airline_line(text: str) -> bool:
    t = text.strip().lower()
    return any(
        x in t for x in [
            "vueling",
            "transavia",
            "klm",
            "british airways",
            "swiss",
        ]
    )


def _is_duration_line(text: str) -> bool:
    return re.fullmatch(r"\d+\s*hr\s*\d+\s*min", text.strip(), flags=re.IGNORECASE) is not None


def _is_route_line(text: str, origin: str, destination: str) -> bool:
    t = text.strip().upper().replace("–", "-").replace("—", "-")
    return t == f"{origin}-{destination}"


def _is_stops_line(text: str) -> bool:
    t = text.strip().lower()
    return t in {"nonstop", "1 stop"}


def _extract_price_from_line(text: str) -> float | None:
    m = re.search(r"€\s?(\d{2,4}(?:[.,]\d{1,2})?)", text)
    if not m:
        return None

    try:
        return float(m.group(1).replace(",", "."))
    except ValueError:
        return None


def _prepare_lines(page_text: str) -> list[str]:
    text = _normalize_text(page_text)
    lines = [line.strip() for line in text.splitlines()]
    return [line for line in lines if line]


def _extract_flight_blocks(page_text: str, origin: str, destination: str) -> list[dict]:
    """
    Parse the Google Flights plain text sequentially.

    Expected pattern in the text:
      time
      -
      time
      airline
      duration
      ORIGIN-DEST
      Nonstop / 1 stop
      ...
      €price
    """
    lines = _prepare_lines(page_text)
    rows: list[dict] = []

    i = 0
    while i < len(lines):
        current = lines[i]

        # Pattern starts with a departure time line
        if not _is_time_line(current):
            i += 1
            continue

        dep_time = current.strip()

        # Often the next non-empty line is "-"
        j = i + 1
        if j < len(lines) and lines[j] == "-":
            j += 1

        if j >= len(lines) or not _is_time_line(lines[j]):
            i += 1
            continue

        arr_time = lines[j].strip()
        j += 1

        if j >= len(lines) or not _is_airline_line(lines[j]):
            i += 1
            continue

        airline = _canonical_airline_name(lines[j])
        j += 1

        if j >= len(lines) or not _is_duration_line(lines[j]):
            i += 1
            continue

        duration = lines[j].strip()
        j += 1

        # Search route and stops in the next few lines
        route_found = False
        stops_value = None
        price_value = None

        scan_limit = min(len(lines), j + 20)
        raw_block_lines = [dep_time, "-", arr_time, airline, duration]

        for k in range(j, scan_limit):
            raw_block_lines.append(lines[k])

            if not route_found and _is_route_line(lines[k], origin, destination):
                route_found = True
                continue

            if route_found and stops_value is None and _is_stops_line(lines[k]):
                stops_value = lines[k].strip()
                continue

            if route_found and price_value is None:
                maybe_price = _extract_price_from_line(lines[k])
                if maybe_price is not None:
                    price_value = maybe_price
                    break

        if route_found and stops_value is not None and price_value is not None:
            rows.append(
                {
                    "airline": airline,
                    "departure_time": dep_time,
                    "arrival_time": arr_time,
                    "duration": duration,
                    "stops": stops_value,
                    "price": price_value,
                    "raw_block": "\n".join(raw_block_lines),
                }
            )

        i += 1

    deduped: list[dict] = []
    seen: set[tuple] = set()

    for row in rows:
        key = (
            row["airline"],
            row["departure_time"],
            row["arrival_time"],
            row["stops"],
            row["price"],
        )
        if key in seen:
            continue
        seen.add(key)
        deduped.append(row)

    return deduped


def _filter_relevant_flights(rows: list[dict], leg_date: date) -> list[dict]:
    allowed_airlines = {"vueling", "transavia"}

    filtered: list[dict] = []

    for row in rows:
        if row["airline"].lower() not in allowed_airlines:
            continue
        if row["stops"].lower() != "nonstop":
            continue
        if not _departure_ok(leg_date, row["departure_time"]):
            continue
        if not (30 <= row["price"] <= 2000):
            continue
        filtered.append(row)

    filtered.sort(key=lambda r: (r["price"], r["departure_time"]))
    return filtered


def _save_debug(
    page,
    safe_label: str,
    url: str,
    response_status: str,
    page_text: str,
    parsed_rows: list[dict],
    filtered_rows: list[dict],
) -> None:
    final_url = page.url
    page_title = page.title()

    screenshot_path = DEBUG_DIR / f"{safe_label}.png"
    html_path = DEBUG_DIR / f"{safe_label}.html"
    txt_path = DEBUG_DIR / f"{safe_label}.txt"

    page.screenshot(path=str(screenshot_path), full_page=True)
    html_path.write_text(page.content(), encoding="utf-8")

    log_lines = [
        f"REQUEST_URL: {url}",
        f"FINAL_URL: {final_url}",
        f"TITLE: {page_title}",
        f"HTTP_STATUS: {response_status}",
        "",
        "=== PARSED ROWS ===",
    ]

    if parsed_rows:
        for row in parsed_rows:
            log_lines.append(
                f"{row['airline']} | {row['departure_time']} - {row['arrival_time']} | "
                f"{row['stops']} | €{row['price']}"
            )
    else:
        log_lines.append("<none>")

    log_lines.extend(["", "=== FILTERED ROWS ==="])

    if filtered_rows:
        for row in filtered_rows:
            log_lines.append(
                f"{row['airline']} | {row['departure_time']} - {row['arrival_time']} | "
                f"{row['stops']} | €{row['price']}"
            )
    else:
        log_lines.append("<none>")

    log_lines.extend(["", "=== PAGE TEXT ===", page_text[:30000]])

    txt_path.write_text("\n".join(log_lines), encoding="utf-8")


def _run_one_leg_search(
    page,
    origin: str,
    destination: str,
    leg_date: date,
    weekend_outbound: date,
    weekend_inbound: date,
) -> list[dict]:
    label = f"{origin}_{destination}_{leg_date.isoformat()}_{weekend_outbound.isoformat()}_{weekend_inbound.isoformat()}"
    safe_label = _safe_name(label)

    url = _build_google_flights_url(
        origin=origin,
        destination=destination,
        leg_date=leg_date.isoformat(),
    )

    print(f"[INFO] Opening {url}")

    response = page.goto(url, wait_until="networkidle", timeout=90000)

    page.wait_for_timeout(10000)
    _maybe_handle_google_interstitials(page)
    page.wait_for_timeout(3000)

    for _ in range(3):
        try:
            page.mouse.wheel(0, 3000)
        except Exception:
            pass
        page.wait_for_timeout(2000)

    page_text = _collect_page_text(page)
    parsed_rows = _extract_flight_blocks(page_text, origin=origin, destination=destination)
    filtered_rows = _filter_relevant_flights(parsed_rows, leg_date=leg_date)

    _save_debug(
        page=page,
        safe_label=safe_label,
        url=url,
        response_status=str(response.status if response else "unknown"),
        page_text=page_text,
        parsed_rows=parsed_rows,
        filtered_rows=filtered_rows,
    )

    results: list[dict] = []

    for row in filtered_rows[:3]:
        results.append(
            {
                "origin": origin,
                "destination": destination,
                "outbound": weekend_outbound,
                "inbound": weekend_inbound,
                "leg_date": leg_date,
                "leg_type": "outbound" if destination == "BCN" else "inbound",
                "airline": row["airline"],
                "outbound_departure": row["departure_time"],
                "outbound_arrival": row["arrival_time"],
                "inbound_departure": "N/A",
                "inbound_arrival": "N/A",
                "outbound_flight_no": "N/A",
                "inbound_flight_no": "N/A",
                "price": row["price"],
                "source_url": page.url,
                "page_title": page.title(),
                "raw_text": row["raw_block"],
            }
        )

    return results


def search_google_flights(pairs: List[Tuple[date, date]]) -> list[dict]:
    DEBUG_DIR.mkdir(parents=True, exist_ok=True)

    results: list[dict] = []

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
            ],
        )

        context = browser.new_context(
            locale="en-GB",
            timezone_id="Europe/Madrid",
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/122.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1440, "height": 2600},
        )

        page = context.new_page()

        for weekend_outbound, weekend_inbound in pairs:
            for airport in ["AMS", "RTM"]:
                try:
                    outbound_rows = _run_one_leg_search(
                        page=page,
                        origin=airport,
                        destination="BCN",
                        leg_date=weekend_outbound,
                        weekend_outbound=weekend_outbound,
                        weekend_inbound=weekend_inbound,
                    )
                    results.extend(outbound_rows)
                except PlaywrightTimeoutError as e:
                    print(f"[ERROR] Timeout outbound {airport}->BCN {weekend_outbound}: {e}")
                except Exception as e:
                    print(f"[ERROR] Outbound {airport}->BCN {weekend_outbound}: {e}")

                try:
                    inbound_rows = _run_one_leg_search(
                        page=page,
                        origin="BCN",
                        destination=airport,
                        leg_date=weekend_inbound,
                        weekend_outbound=weekend_outbound,
                        weekend_inbound=weekend_inbound,
                    )
                    results.extend(inbound_rows)
                except PlaywrightTimeoutError as e:
                    print(f"[ERROR] Timeout inbound BCN->{airport} {weekend_inbound}: {e}")
                except Exception as e:
                    print(f"[ERROR] Inbound BCN->{airport} {weekend_inbound}: {e}")

        context.close()
        browser.close()

    results.sort(
        key=lambda r: (
            r["outbound"],
            r["inbound"],
            r["leg_type"],
            r["origin"],
            r["destination"],
            r["price"],
            r["outbound_departure"],
        )
    )

    return results
