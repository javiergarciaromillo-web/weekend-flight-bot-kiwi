from __future__ import annotations

import re
from pathlib import Path
from typing import List, Tuple
from datetime import date, datetime

from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError


from src.holidays import is_free_day, is_morning_return_workday
from src.planner import allowed_pair

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


def _departure_ok(leg_date: date, departure_time: str, leg_type: str | None = None,
                  arrival_time: str | None = None) -> bool:
    """Local-time eligibility; NCIA holiday weekdays are unrestricted.

    The Monday early-arrival option moves to the first working day after any
    consecutive holidays starting on Monday. The working eve of a Friday
    holiday block uses the normal after-work restriction.
    """
    dep = _parse_time_to_24h(departure_time)
    if dep is None:
        return False
    t = lambda value: datetime.strptime(value, '%H:%M').time()
    weekday = leg_date.weekday()
    if is_free_day(leg_date) and weekday < 6:
        return True
    if leg_type == 'outbound':
        if weekday == 4:
            return dep < t('08:00') or dep >= t('15:30')
        if weekday < 5:
            return dep >= t('17:00')
    if leg_type == 'inbound':
        if weekday == 6:
            return dep >= t('16:00')
        if is_morning_return_workday(leg_date):
            arr = _parse_time_to_24h(arrival_time or '')
            arrives_same_day = '+1' not in (arrival_time or '')
            return (arrives_same_day and arr is not None and dep < arr and arr < t('09:00')) or dep >= t('17:00')
        if weekday < 5:
            return dep >= t('17:00')
    return dep >= t('16:00')


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
    return re.fullmatch(
        r"\d{1,2}:\d{2}\s?(?:AM|PM)(?:\+1)?",
        text.strip(),
        flags=re.IGNORECASE,
    ) is not None


def _is_airline_line(text: str) -> bool:
    t = text.strip().lower()
    return any(
        x in t
        for x in [
            "vueling",
            "transavia",
            "klm",
            "british airways",
            "swiss",
        ]
    )


def _is_duration_line(text: str) -> bool:
    t = text.strip().lower()
    return re.fullmatch(r"\d+\s*hr(?:\s*\d+\s*min)?", t) is not None


def _is_route_line(text: str, origin: str, destination: str) -> bool:
    t = text.strip().upper().replace("–", "-").replace("—", "-")
    return t == f"{origin}-{destination}"


def _is_stops_line(text: str) -> bool:
    t = text.strip().lower()
    return t == "nonstop" or re.fullmatch(r"\d+ stops?", t) is not None


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
    lines = _prepare_lines(page_text)
    rows: list[dict] = []

    i = 0
    while i < len(lines):
        current = lines[i]

        if not _is_time_line(current):
            i += 1
            continue

        dep_time = current.strip()

        j = i + 1
        if j < len(lines) and lines[j] == "-":
            j += 1

        if j >= len(lines) or not _is_time_line(lines[j]):
            i += 1
            continue

        arr_time = lines[j].strip()
        j += 1

        # The route/time/duration structure identifies a flight, including airlines
        # outside our preferences. Airline and stop preferences are applied later.
        # Otherwise a page containing only connecting flights looks like a failure.
        if j + 1 >= len(lines) or not _is_duration_line(lines[j + 1]):
            i += 1
            continue

        airline = _canonical_airline_name(lines[j])
        j += 1

        if j >= len(lines) or not _is_duration_line(lines[j]):
            i += 1
            continue

        duration = lines[j].strip()
        j += 1

        route_found = False
        stops_value = None
        price_value = None

        scan_limit = min(len(lines), j + 20)
        raw_block_lines = [dep_time, "-", arr_time, airline, duration]

        for k in range(j, scan_limit):
            # Never borrow a route or price from the following flight block.
            if _is_time_line(lines[k]):
                break
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


def _filter_relevant_flights(
    rows: list[dict],
    leg_date: date,
    origin: str,
    destination: str,
    allow_klm_from_ams: bool = True,
) -> list[dict]:
    filtered: list[dict] = []

    for row in rows:
        airline = row["airline"].lower()

        airline_ok = airline in {"vueling", "transavia"}

        if allow_klm_from_ams and airline == "klm":
            airline_ok = origin == "AMS" or destination == "AMS"

        if not airline_ok:
            continue

        if row["stops"].lower() != "nonstop":
            continue

        if not _departure_ok(leg_date, row["departure_time"],
                             "outbound" if destination == "BCN" else "inbound",
                             row.get("arrival_time")):
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
    allow_klm_from_ams: bool = True,
) -> list[dict]:
    label = (
        f"{origin}_{destination}_{leg_date.isoformat()}_"
        f"{weekend_outbound.isoformat()}_{weekend_inbound.isoformat()}"
    )
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
    filtered_rows = _filter_relevant_flights(
        rows=parsed_rows,
        leg_date=leg_date,
        origin=origin,
        destination=destination,
        allow_klm_from_ams=allow_klm_from_ams,
    )

    _save_debug(
        page=page,
        safe_label=safe_label,
        url=url,
        response_status=str(response.status if response else "unknown"),
        page_text=page_text,
        parsed_rows=parsed_rows,
        filtered_rows=filtered_rows,
    )

    if not parsed_rows:
        raise ValueError("No flight blocks parsed; availability could not be verified")

    results: list[dict] = []

    for row in filtered_rows:
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


def _bind_leg(rows, outbound, inbound):
    """Apply trip-specific constraints to a verified route/date observation."""
    if not allowed_pair(outbound, inbound):
        return []
    return [dict(row, outbound=outbound, inbound=inbound) for row in rows
            if _departure_ok(row['leg_date'], row['outbound_departure'], row['leg_type'],
                             row.get('outbound_arrival'))]


def recover_failed_queries(pairs, rows, diagnostics, later_rows, later_diagnostics):
    """Reuse successful learning queries while retaining route/airline filters."""
    recovered = {key for key, status in diagnostics.items()
                 if status == 'failed' and later_diagnostics.get(key) in {'ok', 'filtered_empty'}}
    if not recovered:
        return rows
    # Learning repeats a leg across combinations. Deduplicate before rebinding.
    candidates = {}
    for row in later_rows:
        key = (row['origin'], row['destination'], row['leg_date'])
        airline = row['airline'].lower()
        airline_ok = (airline in {'vueling', 'transavia'}
                      or (airline == 'klm' and 'AMS' in key[:2]))
        if key in recovered and airline_ok:
            identity = (row['airline'], row['outbound_departure'], row['outbound_arrival'], row['price'])
            candidates.setdefault(key, {})[identity] = row
    result = list(rows)
    for key in recovered:
        flights = list(candidates.get(key, {}).values())
        diagnostics[key] = 'ok' if flights else 'filtered_empty'
        print(f"[INFO] Recovered {key[0]}->{key[1]} {key[2]} from learning observations")
        for outbound, inbound in pairs:
            if key[2] == (outbound if key[1] == 'BCN' else inbound):
                result.extend(_bind_leg(flights, outbound, inbound))
    return result


def search_google_flights(
    pairs: List[Tuple[date, date]],
    allow_klm_from_ams: bool = True,
    diagnostics: dict | None = None,
) -> list[dict]:
    pairs = [pair for pair in pairs if allowed_pair(*pair)]
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

        cache = {}
        statuses = {}
        queries = {}
        for weekend_outbound, weekend_inbound in pairs:
            for airport in ["AMS", "RTM"]:
                for origin, destination, leg_date in (
                    (airport, "BCN", weekend_outbound),
                    ("BCN", airport, weekend_inbound),
                ):
                    queries.setdefault((origin, destination, leg_date), (weekend_outbound, weekend_inbound))

        def query(key, attempt):
            origin, destination, leg_date = key
            outbound, inbound = queries[key]
            try:
                leg_rows = _run_one_leg_search(
                    page, origin, destination, leg_date, outbound, inbound,
                    allow_klm_from_ams=allow_klm_from_ams,
                )
                cache[key] = leg_rows
                statuses[key] = "ok" if leg_rows else "filtered_empty"
                if attempt > 1:
                    print(f"[INFO] Recovered {origin}->{destination} {leg_date} on attempt {attempt}")
            except Exception as e:
                print(f"[ERROR] Search {origin}->{destination} {leg_date} attempt {attempt}/3: {e}")
                cache[key] = []
                statuses[key] = "failed"

        for key in queries:
            query(key, 1)
        # Retry once the other dates have been visited, rather than hammering
        # the same failing page. Never retry a verified filtered-empty result.
        for attempt, delay_ms in [(2, 2000), (3, 5000)]:
            failed = [key for key in queries if statuses[key] == "failed"]
            if not failed:
                break
            page.wait_for_timeout(delay_ms)
            for key in failed:
                query(key, attempt)

        if diagnostics is not None:
            diagnostics.update(statuses)
        # Build combinations only after retries, so every trip sharing a
        # recovered route/date receives the same final observation.
        for outbound, inbound in pairs:
            for airport in ["AMS", "RTM"]:
                for key in [(airport, "BCN", outbound), ("BCN", airport, inbound)]:
                    results.extend(_bind_leg(cache[key], outbound, inbound))

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
