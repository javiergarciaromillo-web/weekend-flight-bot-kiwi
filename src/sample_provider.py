from __future__ import annotations

from datetime import date
from src.models import FlightOption, Route, DatePair


def get_sample_options(routes: list[Route], pairs: list[DatePair]) -> list[FlightOption]:
    """
    Datos de ejemplo para comprobar:
    - histórico
    - HTML
    - envío de email
    - GitHub Actions
    """
    results: list[FlightOption] = []

    base_prices = [180.18, 186.18, 195.18, 201.99]
    airlines = ["Vueling", "Transavia"]

    for i, pair in enumerate(pairs):
        for route in routes:
            for j in range(2):
                airline = airlines[(i + j) % len(airlines)]
                price = base_prices[(i + j) % len(base_prices)]

                if route.origin == "RTM":
                    price += 8.0

                results.append(
                    FlightOption(
                        origin=route.origin,
                        destination=route.destination,
                        outbound_date=pair.outbound_date,
                        inbound_date=pair.inbound_date,
                        airline=airline,
                        outbound_flight_no=f"OUT{i+1}{j+1}",
                        inbound_flight_no=f"IN{i+1}{j+1}",
                        outbound_departure="16:55" if pair.outbound_date.weekday() == 3 else "20:50",
                        outbound_arrival="19:05" if pair.outbound_date.weekday() == 3 else "23:05",
                        inbound_departure="19:55" if pair.inbound_date.weekday() == 6 else "17:25",
                        inbound_arrival="22:15" if pair.inbound_date.weekday() == 6 else "19:55",
                        total_price_eur=price,
                    )
                )

    return results
