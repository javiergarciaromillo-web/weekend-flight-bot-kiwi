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


def _departure_ok(value: str, min_time: str = "16:00") -> bool:
    dep = _parse_time_to_24h(value)
    if dep is None:
        return False

    threshold = datetime.strptime(min_time, "%H:%M").time()
    return dep >= threshold


def _extract_flight_blocks(page_text: str, origin: str, destination: str) -> list[dict]:
    text = _normalize_text(page_text)

    route_pattern = rf"{re.escape(origin)}-{re.escape(destination)}"

    pattern = re.compile(
        rf"(?P<dep>\d{{1,2}}:\d{{2}}\s?(?:AM|PM))\s*-\s*"
        rf"(?P<arr>\d{{1,2}}:\d{{2}}\s?(?:AM|PM)(?:\+1)?)\s*"
        rf"(?P<airline>VuelingIberia|Transavia|KLM|British Airways|SWISS)\s*"
        rf"(?P<duration>\d+\s*hr\s*\d+\s*min)\s*"
        rf"{route_pattern}\s*"
        rf"(?P<stops>Nonstop|1 stop)\s*"
        rf".*?"
        rf"€(?P<price>\d{{2,4}}(?:[.,]\d{{1,2}})?)",
        flags=re.IGNORECASE | re.DOTALL,
    )

    rows: list[dict] = []

    for match in pattern.finditer(text):
        airline_raw = match.group("airline").strip()

        if "vueling" in airline_raw.lower():
            airline = "Vueling"
        elif "transavia" in airline_raw.lower():
            airline = "Transavia"
        else:
            airline = airline_raw

        try:
            price = float(match.group("price").replace(",", "."))
        except ValueError:
            continue

        rows.append(
            {
                "airline": airline,
                "departure_time": match.group("dep").strip(),
                "arrival_time": match.group("arr").strip(),
                "stops": match.group("stops").strip(),
                "price": price,
                "raw_block": match.group(0),
            }
        )

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


def _filter_relevant_flights(rows: list[dict]) -> list[dict]:
    allowed_airlines = {"vueling", "transavia"}

    filtered: list[dict] = []

    for row in rows:
        if row["airline"].lower() not in allowed_airlines:
            continue
        if row["stops"].lower() != "nonstop":
            continue
        if not _departure_ok(row["departure_time"], "16:00"):
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

    log_lines.extend(["", "=== PAGE TEXT ===", page_text[:20000]])

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
    filtered_rows = _filter_relevant_flights(parsed_rows)

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
                    print(f"[ERROR] Timeout outbound {airport}->{ 'BCN' } {weekend_outbound}: {e}")
                except Exception as e:
                    print(f"[ERROR] Outbound {airport}->{ 'BCN' } {weekend_outbound}: {e}")

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
