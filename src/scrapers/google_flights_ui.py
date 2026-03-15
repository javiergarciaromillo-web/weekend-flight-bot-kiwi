from playwright.async_api import async_playwright
import re
from dataclasses import dataclass

@dataclass
class Flight:
    airline: str
    depart: str
    arrive: str
    price: float


def build_url(origin, destination, depart, return_date):
    return (
        "https://www.google.com/travel/flights?"
        f"hl=en&curr=EUR#flt={origin}.{destination}.{depart}"
        f"*{destination}.{origin}.{return_date};c:EUR;e:1;sd:1;t:f;tt:r"
    )


async def scrape_flights(origin, destination, depart, return_date):

    url = build_url(origin, destination, depart, return_date)

    async with async_playwright() as p:

        browser = await p.chromium.launch(
            headless=True,
            args=["--disable-blink-features=AutomationControlled"]
        )

        page = await browser.new_page()

        await page.goto(url, timeout=60000)

        # esperar resultados reales
        await page.wait_for_timeout(8000)

        # scroll para forzar render
        await page.mouse.wheel(0, 3000)

        await page.wait_for_timeout(4000)

        html = await page.content()

        flights = []

        # buscar precios
        prices = re.findall(r"€\d+", html)

        if not prices:
            print("NO PRICES FOUND")
            await browser.close()
            return []

        price = float(prices[0].replace("€", ""))

        flights.append(
            Flight(
                airline="unknown",
                depart="unknown",
                arrive="unknown",
                price=price
            )
        )

        await browser.close()

        return flights
