from __future__ import annotations

from playwright.sync_api import sync_playwright
from src.models import FlightOption, Route, DatePair


def build_skyscanner_url(origin: str, destination: str, outbound: str, inbound: str) -> str:
    """
    Construye la URL de búsqueda en Skyscanner.
    """
    return (
        f"https://www.skyscanner.net/transport/flights/"
        f"{origin.lower()}/{destination.lower()}/"
        f"{outbound}/{inbound}/?adultsv2=1&cabinclass=economy"
    )


def scrape_skyscanner(routes: list[Route], pairs: list[DatePair]) -> list[FlightOption]:
    """
    Scraper simple de Skyscanner.
    Busca precio mínimo visible para cada combinación.
    """

    results: list[FlightOption] = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        for route in routes:
            for pair in pairs:

                url = build_skyscanner_url(
                    route.origin,
                    route.destination,
                    pair.outbound_date.isoformat(),
                    pair.inbound_date.isoformat(),
                )

                print("Searching:", url)

                try:
                    page.goto(url, timeout=60000)

                    page.wait_for_timeout(8000)

                    prices = page.locator("[data-test-id='price']").all_text_contents()

                    if not prices:
                        continue

                    price = prices[0]
                    price = (
                        price.replace("€", "")
                        .replace(",", "")
                        .strip()
                    )

                    price_value = float(price)

                    results.append(
                        FlightOption(
                            origin=route.origin,
                            destination=route.destination,
                            outbound_date=pair.outbound_date,
                            inbound_date=pair.inbound_date,
                            airline="Unknown",
                            outbound_flight_no="N/A",
                            inbound_flight_no="N/A",
                            outbound_departure="16:00",
                            outbound_arrival="18:00",
                            inbound_departure="18:00",
                            inbound_arrival="20:00",
                            total_price_eur=price_value,
                        )
                    )

                except Exception as e:
                    print("Error scraping", url, e)

        browser.close()

    return results
