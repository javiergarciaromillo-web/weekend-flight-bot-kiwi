from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path
from typing import Optional, Tuple

from playwright.sync_api import sync_playwright


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
    if flight_code not in page_text:
        return None, None, None

    idx = page_text.find(flight_code)
    window = page_text[max(0, idx - 900) : idx + 900]

    times = _extract_time_candidates(window)
    price = _extract_price_eur(window)

    depart = times[0] if len(times) >= 1 else None
    arrive = times[1] if len(times) >= 2 else None

    if depart and not _within(depart, time_from, time_to):
        return None, depart, arrive

    return price, depart, arrive


def _click_cookie_accept(page) -> None:
    for txt in ["OK, LAS ACEPTO", "Aceptar", "Aceptar todo", "Accept", "Accept all"]:
        try:
            page.get_by_role("button", name=txt).click(timeout=2500)
            return
        except Exception:
            pass


def _fill_airport(page, label: str, code: str) -> bool:
    # Click label and type code
    try:
        page.get_by_text(label, exact=True).click(timeout=2000)
        page.keyboard.type(code, delay=25)
        page.wait_for_timeout(500)
        page.keyboard.press("Enter")
        return True
    except Exception:
        pass

    # fallback: first visible input after the label
    try:
        el = page.locator("input").filter(has_text="").first
        el.click(timeout=2000)
        el.fill("", timeout=2000)
        el.type(code, delay=25)
        page.wait_for_timeout(500)
        page.keyboard.press("Enter")
        return True
    except Exception:
        return False


def _open_datepicker_and_pick(page, date_iso: str, dbg: Path, tag: str) -> bool:
    """
    Opens the 'Ida' datepicker and clicks the day number.
    This is best-effort; artifacts will show if selectors differ.
    """
    d = datetime.fromisoformat(date_iso)
    day = str(d.day)

    # open datepicker by clicking "Ida"
    opened = False
    for sel in [
        "text=Ida",
        "text=Fechas de vuelo",
        "input[aria-label*='Ida']",
        "input[placeholder*='Ida']",
        "button:has-text('Ida')",
    ]:
        try:
            page.locator(sel).first.click(timeout=2500)
            opened = True
            break
        except Exception:
            continue

    # Save state after trying to open calendar
    page.wait_for_timeout(1500)
    try:
        page.screenshot(path=str(dbg / f"vueling_calendar_{tag}.png"), full_page=True)
    except Exception:
        pass

    if not opened:
        return False

    # Click day cell (common patterns in calendars)
    candidates = [
        f"button:has-text('{day}')",
        f"[role='button']:has-text('{day}')",
        f"[role='gridcell']:has-text('{day}')",
        f"td:has-text('{day}')",
    ]
    for c in candidates:
        try:
            page.locator(c).first.click(timeout=2500)
            page.wait_for_timeout(600)
            return True
        except Exception:
            continue

    return False


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
        browser = p.chromium.launch(
            headless=True,
            args=["--disable-blink-features=AutomationControlled"],
        )
        page = browser.new_page(
            locale="es-ES",
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/122.0.0.0 Safari/537.36"
            ),
        )
        page.set_default_timeout(15000)
        page.set_default_navigation_timeout(30000)

        try:
            url = "https://www.vueling.com/es"
            print(f"[VUELING] goto {url}")
            page.goto(url, wait_until="load", timeout=30000)
            page.wait_for_timeout(2500)

            _click_cookie_accept(page)
            page.wait_for_timeout(800)

            # Fill from/to using the "Buscar vuelos" widget
            ok_from = _fill_airport(page, "De", origin)
            ok_to = _fill_airport(page, "A", destination)

            # One-way if possible
            try:
                page.get_by_text("Solo ida", exact=False).click(timeout=2000)
            except Exception:
                pass

            ok_date = _open_datepicker_and_pick(
                page, date_iso, dbg, tag=f"{origin}_{destination}_{date_iso}_{flight_code}"
            )

            # Click search
            clicked = False
            for txt in ["BUSCAR", "Buscar"]:
                try:
                    page.get_by_role("button", name=txt).click(timeout=4000)
                    clicked = True
                    break
                except Exception:
                    pass
            if not clicked:
                try:
                    page.get_by_text("BUSCAR", exact=False).click(timeout=4000)
                    clicked = True
                except Exception:
                    pass

            page.wait_for_timeout(9000)

            txt = page.inner_text("body")
            has_code = flight_code in txt
            has_euro = "€" in txt
            print(
                f"[VUELING][DEBUG] filled_from={ok_from} filled_to={ok_to} set_date={ok_date} clicked={clicked} "
                f"{origin}->{destination} {date_iso} {flight_code} has_code={has_code} has_euro={has_euro}"
            )

            price, depart, arrive = _best_match_from_page_text(txt, flight_code, time_from, time_to)
            out["price_eur"] = price
            out["depart"] = depart
            out["arrive"] = arrive

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
