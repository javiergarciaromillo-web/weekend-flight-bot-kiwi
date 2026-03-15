from playwright.sync_api import sync_playwright
from datetime import datetime


def search_flights(pairs):

    results = []

    with sync_playwright() as p:

        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        for origin in ["AMS", "RTM"]:

            for outbound, inbound in pairs:

                url = (
                    f"https://www.skyscanner.net/transport/flights/"
                    f"{origin.lower()}/bcn/"
                    f"{outbound.isoformat()}/{inbound.isoformat()}/"
                )

                try:

                    page.goto(url, timeout=60000)

                    page.wait_for_timeout(8000)

                    prices = page.locator("[data-test-id='price']").all_text_contents()

                    if not prices:
                        continue

                    price = prices[0].replace("€", "").replace(",", "").strip()

                    price = float(price)

                    results.append(
                        {
                            "origin": origin,
                            "destination": "BCN",
                            "outbound": outbound,
                            "inbound": inbound,
                            "price": price,
                        }
                    )

                except Exception as e:

                    print("Error:", e)

        browser.close()

    return results
