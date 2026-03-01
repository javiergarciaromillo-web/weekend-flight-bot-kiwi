from __future__ import annotations

import re
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

    # Apply time filter to DEPART time
    if depart and not _within(depart, time_from, time_to):
        return None, depart, arrive

    return price, depart, arrive


def _click_first(page, candidates: list[tuple[str, str]], timeout_ms: int = 2500) -> bool:
    for kind, value in candidates:
        try:
            if kind == "role":
                role, name = value.split("|", 1)
                page.get_by_role(role, name=name).click(timeout=timeout_ms)
                return True
            if kind == "css":
                page.locator(value).first.click(timeout=timeout_ms)
                return True
            if kind == "text":
                page.get_by_text(value, exact=False).first.click(timeout=timeout_ms)
                return True
        except Exception:
            continue
    return False


def _fill_airport_field(page, label_hints: list[str], code: str) -> bool:
    # Try by label
    for lbl in label_hints:
        try:
            page.get_by_label(lbl).click(timeout=2000)
            page.get_by_label(lbl).fill("", timeout=2000)
            page.get_by_label(lbl).type(code, delay=25)
            page.wait_for_timeout(600)
            page.keyboard.press("Enter")
            return True
        except Exception:
            pass

    # Try common input attributes
    selectors = [
        "input[name*='origin']",
        "input[id*='origin']",
        "input[name*='from']",
        "input[id*='from']",
        "input[aria-label*='Origen']",
        "input[aria-label*='Salida']",
        "input[aria-label*='Destino']",
        "input[name*='destination']",
        "input[id*='destination']",
        "input[name*='to']",
        "input[id*='to']",
    ]

    # Heuristic: just type into the first visible input that looks like an airport field
    inputs = page.locator("input")
    n = inputs.count()
    for i in range(n):
        try:
            el = inputs.nth(i)
            if not el.is_visible():
                continue
            # skip date inputs
            t = (el.get_attribute("type") or "").lower()
            if t == "date":
                continue
            el.click(timeout=1500)
            el.fill("", timeout=1500)
            el.type(code, delay=25)
            page.wait_for_timeout(600)
            page.keyboard.press("Enter")
            return True
        except Exception:
            continue

    # Fallback: try known selectors
    for sel in selectors:
        try:
            el = page.locator(sel).first
            if not el.is_visible():
                continue
            el.click(timeout=2000)
            el.fill("", timeout=2000)
            el.type(code, delay=25)
            page.wait_for_timeout(600)
            page.keyboard.press("Enter")
            return True
        except Exception:
            continue

    return False


def _set_departure_date_best_effort(page, date_iso: str) -> bool:
    # native date input
    try:
        page.locator("input[type='date']").first.fill(date_iso, timeout=2000)
        return True
    except Exception:
        pass

    # common date fields
    for sel in [
        "input[name*='departure']",
        "input[id*='departure']",
        "input[aria-label*='Ida']",
        "input[placeholder*='Ida']",
        "input[aria-label*='Salida']",
        "input[placeholder*='Salida']",
    ]:
        try:
            el = page.locator(sel).first
            el.click(timeout=2000)
            page.evaluate(
                """(el, v) => { try { el.removeAttribute('readonly'); } catch(e) {} el.value = v; el.dispatchEvent(new Event('input', {bubbles:true})); el.dispatchEvent(new Event('change', {bubbles:true})); }""",
                el,
                date_iso,
            )
            return True
        except Exception:
            continue

    return False


def scrape_transavia_price(
    origin: str,
    destination: str,
    date_iso: str,
    flight_code: str,
    time_from: str,
    time_to: str,
) -> dict:
    dbg = _ensure_debug_dir()
    out = {
        "provider": "TRANSAVIA",
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
            url = "https://www.transavia.com/reservar/es-es/buscar-un-vuelo"
            print(f"[TRANSAVIA] goto {url}")
            page.goto(url, wait_until="load", timeout=30000)
            page.wait_for_timeout(2500)

            # Cookies
            _click_first(
                page,
                [
                    ("text", "Aceptar"),
                    ("text", "Aceptar todo"),
                    ("text", "Accept"),
                    ("text", "Accept all"),
                ],
                timeout_ms=3500,
            )
            page.wait_for_timeout(800)

            # Fill origin / destination (best-effort)
            ok_from = _fill_airport_field(page, ["Origen", "Salida", "From"], origin)
            ok_to = _fill_airport_field(page, ["Destino", "Llegada", "To"], destination)

            ok_date = _set_departure_date_best_effort(page, date_iso)

            # Click search
            clicked = _click_first(
                page,
                [
                    ("text", "Buscar"),
                    ("text", "Buscar vuelos"),
                    ("text", "Ver vuelos"),
                    ("text", "Mostrar vuelos"),
                    ("text", "Search"),
                ],
                timeout_ms=5000,
            )

            page.wait_for_timeout(9000)

            txt = page.inner_text("body")
            has_code = flight_code in txt
            has_euro = "€" in txt
            print(
                f"[TRANSAVIA][DEBUG] filled_from={ok_from} filled_to={ok_to} set_date={ok_date} clicked={clicked} "
                f"{origin}->{destination} {date_iso} {flight_code} has_code={has_code} has_euro={has_euro}"
            )

            price, depart, arrive = _best_match_from_page_text(txt, flight_code, time_from, time_to)

            out["price_eur"] = price
            out["depart"] = depart
            out["arrive"] = arrive

            page.screenshot(
                path=str(dbg / f"transavia_{origin}_{destination}_{date_iso}_{flight_code}.png"),
                full_page=True,
            )
            (dbg / f"transavia_{origin}_{destination}_{date_iso}_{flight_code}.txt").write_text(
                txt, encoding="utf-8"
            )

        except Exception as e:
            out["error"] = str(e)
            try:
                page.screenshot(
                    path=str(dbg / f"transavia_ERROR_{origin}_{destination}_{date_iso}_{flight_code}.png"),
                    full_page=True,
                )
            except Exception:
                pass
        finally:
            browser.close()

    return out
