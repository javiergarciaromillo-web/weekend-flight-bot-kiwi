from __future__ import annotations

import re
from pathlib import Path
from datetime import datetime

from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError


DEBUG_DIR = Path("debug")


def _safe_name(text: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_.-]+", "_", text)


def _click_if_present(page, selectors: list[str], timeout: int = 2000) -> bool:
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
            "text='Proceed anyway'",
            "text='Continue anyway'",
            "button:has-text('Proceed anyway')",
            "button:has-text('Continue anyway')",
        ],
        timeout=3000,
    )

    _click_if_present(
        page,
        [
            "button:has-text('Accept all')",
            "button:has-text('I agree')",
            "button:has-text('Aceptar todo')",
            "button:has-text('Acepto')",
        ],
        timeout=3000,
    )


def _build_google_flights_url(origin: str, outbound: str, inbound: str) -> str:
    # Formato legacy muy usado para precargar búsquedas.
    # Puede cambiar en el futuro, por eso dejamos logs y debug.
    return (
        "https://www.google.com/travel/flights"
        f"?hl=en&curr=EUR#flt={origin}.BCN.{outbound}*BCN.{origin}.{inbound};"
        "c:EUR;e:1;sd:1;t:f;tt:r"
    )


def _is_allowed_airline(text: str) -> bool:
    t = text.lower()
    return ("vueling" in t) or ("transavia" in t)


def _has_zero_stops(text: str) -> bool:
    t = text.lower()
    return (
        "nonstop" in t
        or "non-stop" in t
        or "0 stops" in t
        or "0 stop" in t
        or "direct" in t
    )


def _extract_price(text: str) -> float | None:
    # Casos: €180, EUR 180, 180 €
    matches = re.findall(r"(?:€|EUR\s?)(\d{1,4}(?:[.,]\d{1,2})?)|(\d{1,4}(?:[.,]\d{1,2})?)\s?€", text)
    for a, b in matches:
        raw = a or b
        raw = raw.replace(",", ".")
        try:
            return float(raw)
        except ValueError:
            pass
    return None


def _extract_times(text: str) -> tuple[str | None, str | None]:
    times = re.findall(r"\b([01]?\d|2[0-3]):[0-5]\d\b", text)
    full_times = re.findall(r"\b(?:[01]?\d|2[0-3]):[0-5]\d\b", text)

    if len(full_times) >= 2:
        return full_times[0], full_times[1]
    return None, None


def _departure_ok(dep_time: str | None) -> bool:
    if dep_time is None:
        return False
    try:
        return datetime.strptime(dep_time, "%H:%M").time() >= datetime.strptime("16:00", "%H:%M").time()
    except ValueError:
        return False


def _collect_candidate_cards(page) -> list[str]:
    selectors = [
        "[role='listitem']",
        "li",
        "div[role='main'] div",
        "[jscontroller]",
    ]

    texts: list[str] = []
    seen: set[str] = set()

    for selector in selectors:
        try:
            locator = page.locator(selector)
            count = min(locator.count(), 120)
            for i in range(count):
                try:
                    t = locator.nth(i).inner_text(timeout=1000).strip()
                    if not t:
                        continue
                    if len(t) < 40:
                        continue
                    if t in seen:
                        continue
                    seen.add(t)
                    texts.append(t)
                except Exception:
                    pass
        except Exception:
            pass

    return texts


def _parse_cards(
    origin: str,
    outbound,
    inbound,
    final_url: str,
    page_title: str,
    card_texts: list[str],
) -> list[dict]:
    rows: list[dict] = []

    for text in card_texts:
        if not _is_allowed_airline(text):
            continue
        if not _has_zero_stops(text):
            continue

        price = _extract_price(text)
        if price is None:
            continue

        dep_time, arr_time = _extract_times(text)
        if not _departure_ok(dep_time):
            continue

        airline = "Vueling" if "vueling" in text.lower() else "Transavia"

        row = {
            "origin": origin,
            "destination": "BCN",
            "outbound": outbound,
            "inbound": inbound,
            "airline": airline,
            "outbound_departure": dep_time or "N/A",
            "outbound_arrival": arr_time or "N/A",
            "inbound_departure": "N/A",
            "inbound_arrival": "N/A",
            "outbound_flight_no": "N/A",
            "inbound_flight_no": "N/A",
            "price": price,
            "source_url": final_url,
            "page_title": page_title,
            "raw_text": text[:2000],
        }
        rows.append(row)

    rows.sort(key=lambda r: r["price"])
    return rows[:3]


def search_google_flights(pairs) -> list[dict]:
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

        for origin in ["AMS", "RTM"]:
            for outbound, inbound in pairs:
                label = f"{origin}_{outbound.isoformat()}_{inbound.isoformat()}"
                safe_label = _safe_name(label)

                url = _build_google_flights_url(
                    origin=origin,
                    outbound=outbound.isoformat(),
                    inbound=inbound.isoformat(),
                )

                try:
                    print(f"[INFO] Opening {url}")
                    response = page.goto(url, wait_until="domcontentloaded", timeout=90000)

                    page.wait_for_timeout(5000)
                    _maybe_handle_google_interstitials(page)
                    page.wait_for_timeout(7000)

                    final_url = page.url
                    page_title = page.title()

                    try:
                        page.locator("body").press("End")
                        page.wait_for_timeout(2000)
                    except Exception:
                        pass

                    screenshot_path = DEBUG_DIR / f"{safe_label}.png"
                    html_path = DEBUG_DIR / f"{safe_label}.html"
                    txt_path = DEBUG_DIR / f"{safe_label}.txt"

                    page.screenshot(path=str(screenshot_path), full_page=True)
                    html_path.write_text(page.content(), encoding="utf-8")

                    card_texts = _collect_candidate_cards(page)

                    log_lines = [
                        f"REQUEST_URL: {url}",
                        f"FINAL_URL: {final_url}",
                        f"TITLE: {page_title}",
                        f"HTTP_STATUS: {response.status if response else 'unknown'}",
                        "",
                        "=== CANDIDATE TEXT BLOCKS ===",
                    ]
                    log_lines.extend(card_texts[:50])

                    txt_path.write_text("\n".join(log_lines), encoding="utf-8")

                    parsed = _parse_cards(
                        origin=origin,
                        outbound=outbound,
                        inbound=inbound,
                        final_url=final_url,
                        page_title=page_title,
                        card_texts=card_texts,
                    )

                    print(f"[INFO] {label}: parsed {len(parsed)} rows")
                    results.extend(parsed)

                except PlaywrightTimeoutError as e:
                    err_path = DEBUG_DIR / f"{safe_label}_error.txt"
                    err_path.write_text(f"Timeout: {e}", encoding="utf-8")
                    try:
                        page.screenshot(path=str(DEBUG_DIR / f"{safe_label}_timeout.png"), full_page=True)
                    except Exception:
                        pass
                    print(f"[ERROR] Timeout in {label}: {e}")

                except Exception as e:
                    err_path = DEBUG_DIR / f"{safe_label}_error.txt"
                    err_path.write_text(str(e), encoding="utf-8")
                    try:
                        page.screenshot(path=str(DEBUG_DIR / f"{safe_label}_error.png"), full_page=True)
                    except Exception:
                        pass
                    print(f"[ERROR] {label}: {e}")

        context.close()
        browser.close()

    deduped: list[dict] = []
    seen_keys: set[tuple] = set()

    for r in results:
        key = (
            r["origin"],
            r["outbound"].isoformat(),
            r["inbound"].isoformat(),
            r["airline"],
            r["outbound_departure"],
            r["price"],
        )
        if key in seen_keys:
            continue
        seen_keys.add(key)
        deduped.append(r)

    deduped.sort(key=lambda r: (r["outbound"], r["inbound"], r["price"]))
    return deduped
