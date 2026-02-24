import os
import requests

API_URL = "https://kiwi-com-cheap-flights.p.rapidapi.com/round-trip"
API_HOST = "kiwi-com-cheap-flights.p.rapidapi.com"


def fetch_round_trip(source: str, destination: str, nights: int, currency: str = "EUR", limit: int = 200) -> dict:
    querystring = {
        "source": source,
        "destination": destination,
        "currency": currency,
        "locale": "en",
        "adults": "1",
        "children": "0",
        "infants": "0",
        "handbags": "1",
        "holdbags": "0",
        "cabinClass": "ECONOMY",
        "sortBy": "PRICE",
        "sortOrder": "ASCENDING",
        "transportTypes": "FLIGHT",
        "limit": str(limit),
        "nightsInDestinationFrom": str(nights),
        "nightsInDestinationTo": str(nights),
        "outbound": "THURSDAY,FRIDAY",
        "inbound": "SUNDAY,MONDAY",
    }

    headers = {
        "X-RapidAPI-Key": os.environ["RAPIDAPI_KEY"],
        "X-RapidAPI-Host": API_HOST,
    }

    r = requests.get(API_URL, headers=headers, params=querystring, timeout=30)
    r.raise_for_status()
    return r.json()
