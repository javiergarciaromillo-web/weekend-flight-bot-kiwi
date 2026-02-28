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

    # Apply outbound time filter to DEPART time
    if depart and not _within(depart, time_from, time_to):
        return None, depart, arrive

    return price, depart, arrive


def _click_first(page, candidates: list[tuple[str, str]], timeout_ms: int = 2500) -> bool:
    """
    candidates: list of (kind, value) where kind in {"role", "css", "text"}.
    """
    for kind, value in candidates:
        try:
            if kind == "role":
                # value format: "button|NAME"
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


def _fill_airport_field(page, label_text: str, code: str) -> bool:
    """
    Tries a bunch of strategies to fill "De" / "A" fields on Vueling public site.
    """
    # 1) get_by_label often works if the field is properly labelled
    try:
        page.get_by_label(label_text).click(timeout=2000)
        page.get_by_label(label_text).fill("", timeout=2000)
        page.get_by_label(label_text).type(code, delay=25)
        page.wait_for_timeout(500)
        page.keyboard.press("Enter")
        return True
    except Exception:
        pass

    # 2) placeholder based
    selectors = [
        f"input[placeholder='{label_text}']",
        f"input[aria-label='{label_text}']",
        f"input[aria-label*='{label_text}']",
    ]
    for sel in selectors:
        try:
            el = page.locator(sel).first
            el.click(timeout=2000)
            el.fill("", timeout=2000)
            el.type(code, delay=25)
            page.wait_for_timeout(500)
            page.keyboard.press("Enter")
            return True
        except Exception:
            continue

    # 3) heuristic: click near visible text "De"/"A" then type
    try:
        page.get_by_text(label_text, exact=True).click(timeout=2000)
        page.keyboard.type(code, delay=25)
        page.wait_for_timeout(500)
        page.keyboard.press("Enter")
        return True
    except Exception:
        pass

    return False


def _set_departure_date_best_effort(page, date_iso: str) -> bool:
    """
    Vueling often uses a datepicker with readonly inputs.
    We try multiple approaches; if none work, artifacts will show what's needed.
    """
    # 1) native date input
    try:
        page.locator("input[type='date']").first.fill(date_iso, timeout=2000)
        return True
    except Exception:
        pass

    # 2) common names
    for sel in [
        "input[name*='departure']",
        "input[name*='outbound']",
        "input[id*='departure']",
        "input[id*='outbound']",
        "input[aria-label*='Ida']",
        "input[placeholder*='Ida']",
    ]:
        try:
            el = page.locator(sel).first
            el.click(timeout=2000)
            # remove readonly and set value via JS if needed
            page.evaluate(
                """(el, v) => { try { el.removeAttribute('readonly'); } catch(e) {} el.value = v; el.dispatchEvent(new Event('input', {bubbles:true})); el.dispatchEvent(new Event('change', {bubbles:true})); }""",
                el,
                date_iso,
            )
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
            # Start at the public Vueling site (more reliable than tickets.* redirects)
            url = "https://www.vueling.com/es"
            print(f"[VUELING] goto {url}")
            page.goto(url, wait_until="load", timeout=30000)
            page.wait_for_timeout(2500)

            # Cookies banner
            _click_first(
                page,
                [
                    ("role", "button|OK, LAS ACEPTO"),
                    ("role", "button|Aceptar"),
                    ("role", "button|Aceptar todo"),
                    ("text", "OK, LAS ACEPTO"),
                    ("text", "ACEPTO"),
                ],
                timeout_ms=3000,
            )
            page.wait_for_timeout(1000)

            # Ensure we are in "Buscar vuelos" widget
            # (If not visible, click "VUELOS" top nav)
            _click_first(
                page,
                [
                    ("text", "VUELOS"),
                    ("text", "Buscar vuelos"),
                ],
                timeout_ms=2500,
            )
            page.wait_for_timeout(1200)

            # Force One-way ("Solo ida" / "Ida")
            _click_first(
                page,
                [
                    ("text", "Solo ida"),
                    ("text", "Ida"),
                ],
                timeout_ms=2000,
            )
            page.wait_for_timeout(600)

            # Fill airports
            ok_from = _fill_airport_field(page, "De", origin)
            ok_to = _fill_airport_field(page, "A", destination)

            # Set date (best-effort)
            ok_date = _set_departure_date_best_effort(page, date_iso)

            # Set passengers: leave default 1 adult (your requirement)

            # Click search
            clicked = _click_first(
                page,
                [
                    ("role", "button|BUSCAR"),
                    ("text", "BUSCAR"),
                    ("text", "Buscar"),
                    ("role", "button|Buscar"),
                ],
                timeout_ms=4000,
            )

            # Wait for navigation / results
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

            # Always save artifacts
            page.screenshot(
                path=str(dbg / f"vueling_{origin}_{destination}_{date_iso}_{flight_code}.png"),
                full_page=True,
            )
            (dbg / f"vueling_{origin}_{destination}_{date_iso}_{flight_code}.txt").write_text(
                txt, encoding="utf-8"
            )

        except Exception as e:
            out["error"] = str(e)
            try:
                page.screenshot(
                    path=str(dbg / f"vueling_ERROR_{origin}_{destination}_{date_iso}_{flight_code}.png"),
                    full_page=True,
                )
            except Exception:
                pass
        finally:
            browser.close()

    return out
