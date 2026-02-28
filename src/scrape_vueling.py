from __future__ import annotations

import re
from pathlib import Path
from typing import Optional, Tuple

from playwright.sync_api import Page, sync_playwright


def _ensure_debug_dir() -> Path:
    p = Path("debug")
    p.mkdir(parents=True, exist_ok=True)
    return p


def _within(hhmm: str, t_from: str, t_to: str) -> bool:
    return t_from <= hhmm <= t_to


def _extract_time_candidates(text: str) -> list[str]:
    return re.findall(r"\b\d{2}:\d{2}\b", text)


def _extract_price_eur(text: str) -> Optional[float]:
    m = re.search(r"€\s*([0-9]+(?:[.,][0-9]+)?)", text)
    if not m:
        return None
    return float(m.group(1).replace(",", "."))


def _best_match_from_page_text(
    page_text: str,
    flight_code: str,
    time_from: str,
    time_to: str,
) -> Tuple[Optional[float], Optional[str], Optional[str]]:
    # Best-effort: find the line/block containing the flight_code, then parse times and price nearby.
    if flight_code not in page_text:
        return None, None, None

    # Split into chunks around flight_code occurrences
    idx = page_text.find(flight_code)
    window = page_text[max(0, idx - 500) : idx + 500]

    times = _extract_time_candidates(window)
    price = _extract_price_eur(window)

    depart = times[0] if len(times) >= 1 else None
    arrive = times[1] if len(times) >= 2 else None

    if depart and not _within(depart, time_from, time_to):
        return None, depart, arrive

    return price, depart, arrive


def scrape_vueling_price(
    origin: str,
    destination: str,
    date_iso: str,
    flight_code: str,
    time_from: str,
    time_to: str,
) -> dict:
    dbg = _ensure_debug_dir()
    out = {
        "provider": "VUELING",
        "origin": origin,
        "destination": destination,
        "date": date_iso,
        "flight_code": flight_code,
        "price_eur": None,
        "depart": None,
        "arrive": None,
        "error": None,
    }

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(locale="es-ES")

        try:
            page.goto("https://tickets.vueling.com/booking/selectFlight", wait_until="domcontentloaded", timeout=60000)

            # Cookies (best-effort)
            for txt in ["Aceptar", "Aceptar todo", "Accept", "Accept all"]:
                try:
                    page.get_by_role("button", name=txt).click(timeout=2500)
                    break
                except Exception:
                    pass

            # NOTE: Vueling UI changes often. We use best-effort selectors + page text fallback.
            # Try to fill origin/destination by searching for input fields.
            # If this fails, the debug screenshot + html will help adjust.
            page.wait_for_timeout(1500)

            # Try to find any input and type airport code then pick dropdown
            inputs = page.locator("input")
            n = inputs.count()

            # Heuristic: type origin/destination in first two visible text inputs
            typed = 0
            for i in range(n):
                try:
                    el = inputs.nth(i)
                    if not el.is_visible():
                        continue
                    el.click(timeout=1000)
                    # clear and type
                    el.fill("", timeout=1000)
                    if typed == 0:
                        el.type(origin, delay=20)
                        page.wait_for_timeout(600)
                        page.keyboard.press("Enter")
                        typed += 1
                        continue
                    if typed == 1:
                        el.type(destination, delay=20)
                        page.wait_for_timeout(600)
                        page.keyboard.press("Enter")
                        typed += 1
                        break
                except Exception:
                    continue

            # Date: try any input[type=date], else type into any visible date-like input
            try:
                page.locator("input[type='date']").first.fill(date_iso, timeout=2000)
            except Exception:
                # fallback: type date_iso into a focused field if calendar uses text
                try:
                    page.keyboard.type(date_iso, delay=15)
                except Exception:
                    pass

            # Search button (best-effort)
            clicked = False
            for txt in ["Buscar", "Search", "Continuar", "Continue"]:
                try:
                    page.get_by_role("button", name=txt).click(timeout=3000)
                    clicked = True
                    break
                except Exception:
                    pass
            if not clicked:
                # fallback: click any primary button
                try:
                    page.locator("button").first.click(timeout=2000)
                except Exception:
                    pass

            # Wait for results to load
            page.wait_for_timeout(8000)

            # Extract from full page text (robust fallback)
            txt = page.inner_text("body")
            price, depart, arrive = _best_match_from_page_text(txt, flight_code, time_from, time_to)

            out["price_eur"] = price
            out["depart"] = depart
            out["arrive"] = arrive

            # Save debug artifacts always (first runs are about tuning)
            page.screenshot(path=str(dbg / f"vueling_{origin}_{destination}_{date_iso}_{flight_code}.png"), full_page=True)
            (dbg / f"vueling_{origin}_{destination}_{date_iso}_{flight_code}.txt").write_text(txt, encoding="utf-8")

        except Exception as e:
            out["error"] = str(e)
            try:
                page.screenshot(path=str(dbg / f"vueling_ERROR_{origin}_{destination}_{date_iso}_{flight_code}.png"), full_page=True)
            except Exception:
                pass
        finally:
            browser.close()

    return out
