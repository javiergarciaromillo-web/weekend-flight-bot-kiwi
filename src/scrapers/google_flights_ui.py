from __future__ import annotations

import re
from pathlib import Path

from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError


DEBUG_DIR = Path("debug")


def _safe_name(text: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_.-]+", "_", text)


def _build_google_flights_url(origin: str, outbound: str, inbound: str) -> str:
    return (
        "https://www.google.com/travel/flights/search"
        f"?hl=en&curr=EUR"
        f"&q=Flights%20from%20{origin}%20to%20BCN%20{outbound}%20return%20{inbound}"
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


def _extract_price_candidates(text: str) -> list[float]:
    prices: list[float] = []

    patterns = [
        r"€\s?(\d{1,4}(?:[.,]\d{1,2})?)",
        r"from €\s?(\d{1,4}(?:[.,]\d{1,2})?)",
        r"(\d{1,4}(?:[.,]\d{1,2})?)\s?€",
        r"EUR\s?(\d{1,4}(?:[.,]\d{1,2})?)",
    ]

    for pattern in patterns:
        for match in re.findall(pattern, text, flags=re.IGNORECASE):
            raw = match.replace(",", ".")
            try:
                prices.append(float(raw))
            except ValueError:
                pass

    return prices


def _contains_route(text: str, origin: str) -> bool:
    t = text.lower()
    return (
        origin.lower() in t
        and "bcn" in t
    ) or (
        origin.lower() in t
        and "barcelona" in t
    )


def _is_relevant_block(text: str, origin: str) -> bool:
    t = text.lower()

    bad_signals = [
        "find cheap flights from united states to anywhere",
        "popular flight destinations from united states",
        "search more flights",
        "chicago",
        "dallas",
        "atlanta",
        "new york",
        "los angeles",
        "las vegas",
        "orlando",
        "explore destinations",
    ]
    if any(signal in t for signal in bad_signals):
        return False

    good_signals = [
        origin.lower(),
        "barcelona",
        "bcn",
        "round trip",
        "sort by",
        "price graph",
        "departure",
        "return",
        "stops",
        "nonstop",
        "google flights",
    ]

    return any(signal in t for signal in good_signals)


def _collect_candidate_texts(page, origin: str) -> list[str]:
    selectors = [
        "[role='main']",
        "main",
        "body",
        "[role='listitem']",
        "li",
        "div",
    ]

    texts: list[str] = []
    seen: set[str] = set()

    for selector in selectors:
        try:
            locator = page.locator(selector)
            count = min(locator.count(), 250)
            for i in range(count):
                try:
                    t = locator.nth(i).inner_text(timeout=800).strip()
                    if not t:
                        continue
                    if len(t) < 20:
                        continue
                    if t in seen:
                        continue
                    if not _is_relevant_block(t, origin):
                        continue
                    seen.add(t)
                    texts.append(t)
                except Exception:
                    pass
        except Exception:
            pass

    return texts


def _extract_best_price_from_texts(texts: list[str]) -> float | None:
    all_prices: list[float] = []

    for text in texts:
        all_prices.extend(_extract_price_candidates(text))

    valid_prices = [p for p in all_prices if 20 <= p <= 2000]
    if not valid_prices:
        return None

    return min(valid_prices)


def _save_debug(page, safe_label: str, url: str, response_status: str, candidate_texts: list[str]) -> None:
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
        "=== CANDIDATE TEXT BLOCKS ===",
    ]
    log_lines.extend(candidate_texts[:100])

    txt_path.write_text("\n".join(log_lines), encoding="utf-8")


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
                    response = page.goto(url, wait_until="networkidle", timeout=90000)

                    page.wait_for_timeout(12000)
                    _maybe_handle_google_interstitials(page)
                    page.wait_for_timeout(3000)

                    for _ in range(3):
                        try:
                            page.mouse.wheel(0, 2500)
                        except Exception:
                            pass
                        page.wait_for_timeout(2500)

                    candidate_texts = _collect_candidate_texts(page, origin=origin)

                    _save_debug(
                        page=page,
                        safe_label=safe_label,
                        url=url,
                        response_status=str(response.status if response else "unknown"),
                        candidate_texts=candidate_texts,
                    )

                    best_price = _extract_best_price_from_texts(candidate_texts)

                    if best_price is None:
                        print(f"[WARN] No valid price found for {label}")
                        continue

                    print(f"[OK] {label}: best price {best_price}")

                    results.append(
                        {
                            "origin": origin,
                            "destination": "BCN",
                            "outbound": outbound,
                            "inbound": inbound,
                            "airline": "Unknown",
                            "outbound_departure": "N/A",
                            "outbound_arrival": "N/A",
                            "inbound_departure": "N/A",
                            "inbound_arrival": "N/A",
                            "outbound_flight_no": "N/A",
                            "inbound_flight_no": "N/A",
                            "price": best_price,
                            "source_url": page.url,
                            "page_title": page.title(),
                            "raw_text": "\n\n".join(candidate_texts[:20]),
                        }
                    )

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
            r["price"],
        )
        if key in seen_keys:
            continue
        seen_keys.add(key)
        deduped.append(r)

    deduped.sort(key=lambda r: (r["outbound"], r["inbound"], r["price"]))
    return deduped
