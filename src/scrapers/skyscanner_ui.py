from __future__ import annotations

import re
from pathlib import Path
from playwright.sync_api import sync_playwright


DEBUG_DIR = Path("debug")


def _safe_name(text: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_.-]+", "_", text)


def _extract_first_price_from_texts(texts: list[str]) -> float | None:
    for text in texts:
        cleaned = text.strip()
        if not cleaned:
            continue

        # Casos típicos: "€123", "123 €", "EUR 123", "123"
        match = re.search(r"(\d{1,4}(?:[.,]\d{1,2})?)", cleaned)
        if not match:
            continue

        raw = match.group(1).replace(",", ".")
        try:
            return float(raw)
        except ValueError:
            continue

    return None


def _collect_candidate_texts(page) -> dict[str, list[str]]:
    selectors = {
        "data_test_price": "[data-test-id='price']",
        "price_class_contains": "[class*='price']",
        "money_text": "text=/€|EUR/i",
        "main_cards": "[class*='FlightsTicket']",
        "generic_buttons": "button",
    }

    out: dict[str, list[str]] = {}

    for name, selector in selectors.items():
        try:
            locator = page.locator(selector)
            count = min(locator.count(), 20)
            texts = []
            for i in range(count):
                try:
                    t = locator.nth(i).inner_text(timeout=2000).strip()
                    if t:
                        texts.append(t)
                except Exception:
                    pass
            out[name] = texts
        except Exception:
            out[name] = []

    return out


def search_flights(pairs):

    results = []
    DEBUG_DIR.mkdir(parents=True, exist_ok=True)

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
            viewport={"width": 1440, "height": 2200},
        )

        page = context.new_page()

        for origin in ["AMS", "RTM"]:
            for outbound, inbound in pairs:
                label = f"{origin}_{outbound.isoformat()}_{inbound.isoformat()}"
                safe_label = _safe_name(label)

                url = (
                    f"https://www.skyscanner.net/transport/flights/"
                    f"{origin.lower()}/bcn/"
                    f"{outbound.isoformat()}/{inbound.isoformat()}/"
                )

                try:
                    print(f"[INFO] Opening {url}")
                    response = page.goto(url, wait_until="domcontentloaded", timeout=90000)

                    page.wait_for_timeout(12000)

                    final_url = page.url
                    title = page.title()

                    print(f"[INFO] Final URL: {final_url}")
                    print(f"[INFO] Title: {title}")
                    if response is not None:
                        print(f"[INFO] HTTP status: {response.status}")

                    page.screenshot(path=str(DEBUG_DIR / f"{safe_label}.png"), full_page=True)
                    html = page.content()
                    (DEBUG_DIR / f"{safe_label}.html").write_text(html, encoding="utf-8")

                    candidate_texts = _collect_candidate_texts(page)

                    log_lines = [
                        f"REQUEST_URL: {url}",
                        f"FINAL_URL: {final_url}",
                        f"TITLE: {title}",
                    ]

                    if response is not None:
                        log_lines.append(f"HTTP_STATUS: {response.status}")

                    for selector_name, texts in candidate_texts.items():
                        log_lines.append(f"\n## {selector_name}")
                        if texts:
                            log_lines.extend(texts[:20])
                        else:
                            log_lines.append("<empty>")

                    (DEBUG_DIR / f"{safe_label}.txt").write_text(
                        "\n".join(log_lines),
                        encoding="utf-8",
                    )

                    # Intento de extracción
                    merged_texts = []
                    for texts in candidate_texts.values():
                        merged_texts.extend(texts)

                    price = _extract_first_price_from_texts(merged_texts)

                    if price is None:
                        print(f"[WARN] No price found for {label}")
                        continue

                    print(f"[OK] {label} -> {price}")

                    results.append(
                        {
                            "origin": origin,
                            "destination": "BCN",
                            "outbound": outbound,
                            "inbound": inbound,
                            "price": price,
                            "source_url": final_url,
                            "page_title": title,
                        }
                    )

                except Exception as e:
                    print(f"[ERROR] {label}: {e}")
                    try:
                        page.screenshot(path=str(DEBUG_DIR / f"{safe_label}_error.png"), full_page=True)
                        (DEBUG_DIR / f"{safe_label}_error.txt").write_text(str(e), encoding="utf-8")
                    except Exception:
                        pass

        context.close()
        browser.close()

    return results
