import os
import requests
from datetime import date

API_URL = "https://kiwi-com-cheap-flights.p.rapidapi.com/round-trip"
API_HOST = "kiwi-com-cheap-flights.p.rapidapi.com"


def fetch_round_trip_by_dates(
    source: str,
    destination: str,
    departure_date: date,
    return_date: date,
    currency: str = "EUR",
    limit: int = 200,
) -> dict:
    # Candidate parameter names (wrapper-dependent)
    date_params = {
        # common “explicit dates”
        "departureDate": departure_date.isoformat(),
        "returnDate": return_date.isoformat(),
        "departure_date": departure_date.isoformat(),
        "return_date": return_date.isoformat(),
        "outboundDate": departure_date.isoformat(),
        "inboundDate": return_date.isoformat(),
        "outbound_date": departure_date.isoformat(),
        "inbound_date": return_date.isoformat(),
        # sometimes these exist in “from/to” form but can accept exact date
        "dateFrom": departure_date.isoformat(),
        "dateTo": departure_date.isoformat(),
    }

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
        # IMPORTANT: do NOT use nights here; we want explicit dates
        **date_params,
    }

    headers = {
        "X-RapidAPI-Key": os.environ["RAPIDAPI_KEY"],
        "X-RapidAPI-Host": API_HOST,
    }

    r = requests.get(API_URL, headers=headers, params=querystring, timeout=30)
    r.raise_for_status()
    return r.json()
