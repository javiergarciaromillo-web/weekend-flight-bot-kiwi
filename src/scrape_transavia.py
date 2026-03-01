from __future__ import annotations

import re
from pathlib import Path
from typing import Optional

from playwright.sync_api import sync_playwright


def _ensure_debug_dir() -> Path:
    p = Path("debug")
    p.mkdir(parents=True, exist_ok=True)
    return p


def _extract_all_prices(text: str) -> list[float]:
    vals = []
    for m in re.finditer(r"€\s*([0-9]+(?:[.,][0-9]+)?)", text):
        try:
            vals.append(float(m.group(1).replace(",", ".")))
        except Exception:
            continue
    return vals


def scrape_transavia_price(
    origin: str,
    destination: str,
    date_iso: str,
    flight_code: str,
    time_from: str,
    time_to: str,
) -> dict:

    dbg = _ensure_debug_dir()

    result = {
        "provider": "TRANSAVIA",
        "origin": origin,
        "destination": destination,
        "date": date_iso,
        "flight_code": flight_code,
        "price_eur": None,
        "depart": None,
        "arrive": None,
        "error": None,
        "mode": None,
    }

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=["--disable-blink-features=AutomationControlled"],
        )

        page = browser.new_page(
            locale="es-ES",
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/122.0.0.0 Safari/537.36",
        )

        page.set_default_timeout(15000)

        try:
            url = "https://www.transavia.com/reservar/es-es/buscar-un-vuelo"
            print(f"[TRANSAVIA] goto {url}", flush=True)
            page.goto(url, wait_until="load")
            page.wait_for_timeout(3000)

            # Accept cookies
            for txt in ["Aceptar", "Aceptar todo"]:
                try:
                    page.get_by_text(txt, exact=False).first.click(timeout=2000)
                    break
                except Exception:
                    pass

            page.wait_for_timeout(1500)

            # STATE DUMP
            current_url = page.url
            title = page.title()
            print(f"[TRANSAVIA][STATE] url={current_url} title={title}", flush=True)

            html = page.content()
            (dbg / f"transavia_{origin}_{destination}_{date_iso}_{flight_code}.html").write_text(
                html, encoding="utf-8"
            )

            page.screenshot(
                path=str(dbg / f"transavia_{origin}_{destination}_{date_iso}_{flight_code}.png"),
                full_page=True,
            )

            body_text = page.inner_text("body")

            if flight_code in body_text:
                result["mode"] = "CODE"
                prices = _extract_all_prices(body_text)
                result["price_eur"] = min(prices) if prices else None
            else:
                result["mode"] = "MIN"
                prices = _extract_all_prices(body_text)
                result["price_eur"] = min(prices) if prices else None

        except Exception as e:
            result["error"] = str(e)

        finally:
            browser.close()

    return result
