import os
import requests
from datetime import date, timedelta

API_URL = "https://kiwi-com-cheap-flights.p.rapidapi.com/round-trip"
API_HOST = "kiwi-com-cheap-flights.p.rapidapi.com"


def fetch_round_trip(
    source: str,
    destination: str,
    nights: int,
    currency: str = "EUR",
    limit: int = 200,
    weeks: int = 5,
) -> dict:
    today = date.today()
    end = today + timedelta(days=7 * weeks)

    # Different wrappers use different parameter names for date ranges.
    # We set multiple; the API will use the ones it recognizes.
    date_params = {
        "dateFrom": today.isoformat(),
        "dateTo": end.isoformat(),
        "date_from": today.isoformat(),
        "date_to": end.isoformat(),
        "departureDateFrom": today.isoformat(),
        "departureDateTo": end.isoformat(),
        "outboundDateFrom": today.isoformat(),
        "outboundDateTo": end.isoformat(),
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
        "nightsInDestinationFrom": str(nights),
        "nightsInDestinationTo": str(nights),
        "outbound": "THURSDAY,FRIDAY",
        # inbound is unreliable in this wrapper; we filter inbound weekday in code
        **date_params,
    }

    headers = {
        "X-RapidAPI-Key": os.environ["RAPIDAPI_KEY"],
        "X-RapidAPI-Host": API_HOST,
    }

    r = requests.get(API_URL, headers=headers, params=querystring, timeout=30)
    r.raise_for_status()
    return r.json()
