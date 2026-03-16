from __future__ import annotations

import re
from pathlib import Path
from typing import List, Tuple
from datetime import date

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


def _collect_candidate_texts(page, origin: str) -> list[str]:
    """
    Extract the entire visible text of the page.
    Google Flights changes DOM frequently so parsing
    the whole page is the most robust approach.
    """

    texts: list[str] = []

    try:
        body_text = page.inner_text("body")
        if body_text:
            texts.append(body_text)
    except Exception:
        pass

    return texts


def _extract_best_price_from_texts(texts: list[str]) -> float | None:
    """
    Extract € prices from page text and return lowest realistic one.
    """

    if not texts:
        return None

    all_text = "\n".join(texts)

    matches = re.findall(r"€\s?(\d{2,4})", all_text)

    if not matches:
        return None

    prices: list[float] = []

    for m in matches:
        try:
            prices.append(float(m))
        except ValueError:
            continue

    prices = [p for p in prices if 30 <= p <= 2000]

    if not prices:
        return None

    return min(prices)


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
        "=== PAGE TEXT ===",
    ]

    log_lines.extend(candidate_texts[:5])

    txt_path.write_text("\n".join(log_lines), encoding="utf-8")


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

                    page.wait_for_timeout(10000)

                    _maybe_handle_google_interstitials(page)

                    page.wait_for_timeout(3000)

                    for _ in range(3):
                        try:
                            page.mouse.wheel(0, 3000)
                        except Exception:
                            pass
                        page.wait_for_timeout(2000)

                    candidate_texts = _collect_candidate_texts(page, origin)

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
                            "price": best_price,
                            "source_url": page.url,
                            "page_title": page.title(),
                        }
                    )

                except PlaywrightTimeoutError as e:

                    err_path = DEBUG_DIR / f"{safe_label}_timeout.txt"
                    err_path.write_text(str(e), encoding="utf-8")

                    try:
                        page.screenshot(
                            path=str(DEBUG_DIR / f"{safe_label}_timeout.png"),
                            full_page=True,
                        )
                    except Exception:
                        pass

                    print(f"[ERROR] Timeout in {label}: {e}")

                except Exception as e:

                    err_path = DEBUG_DIR / f"{safe_label}_error.txt"
                    err_path.write_text(str(e), encoding="utf-8")

                    try:
                        page.screenshot(
                            path=str(DEBUG_DIR / f"{safe_label}_error.png"),
                            full_page=True,
                        )
                    except Exception:
                        pass

                    print(f"[ERROR] {label}: {e}")

        context.close()
        browser.close()

    results.sort(key=lambda r: (r["outbound"], r["inbound"], r["price"]))

    return results
