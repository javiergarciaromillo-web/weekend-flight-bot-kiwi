import os
import requests
from datetime import date, datetime, timedelta

API_URL = "https://kiwi-com-cheap-flights.p.rapidapi.com/round-trip"
API_HOST = "kiwi-com-cheap-flights.p.rapidapi.com"


def _dt_start(d: date) -> str:
    # API expects: 2023-07-22T00:00:00
    return datetime(d.year, d.month, d.day, 0, 0, 0).strftime("%Y-%m-%dT%H:%M:%S")


def _dt_end(d: date) -> str:
    # inclusive end of day
    return datetime(d.year, d.month, d.day, 23, 59, 59).strftime("%Y-%m-%dT%H:%M:%S")


def fetch_round_trip_window(
    source: str,
    destination: str,
    *,
    start_date: date,
    end_date: date,
    currency: str = "EUR",
    locale: str = "en",
    adults: int = 1,
    max_stops: int = 0,
    limit: int = 200,
) -> dict:
    """
    Search within a departure/return date window (next 5 weeks).
    IMPORTANT: parameter name is 'outboundDepartmentDateStart/End' (typo in API).
    """

    querystring = {
        "source": source,
        "destination": destination,
        "currency": currency,
        "locale": locale,
        "adults": str(adults),
        "children": "0",
        "infants": "0",
        "handbags": "1",
        "holdbags": "0",
        "cabinClass": "ECONOMY",
        "sortBy": "PRICE",
        "sortOrder": "ASCENDING",
        "maxStopsCount": str(max_stops),
        "transportTypes": "FLIGHT",
        "limit": str(limit),

        # Only allow outbound departures Thu/Fri
        "outbound": "THURSDAY,FRIDAY",

        # Date windows (THIS is what makes it work)
        "outboundDepartmentDateStart": _dt_start(start_date),
        "outboundDepartmentDateEnd": _dt_end(end_date),
        "inboundDepartureDateStart": _dt_start(start_date),
        "inboundDepartureDateEnd": _dt_end(end_date),
    }

    headers = {
        "x-rapidapi-key": os.environ["RAPIDAPI_KEY"],
        "x-rapidapi-host": API_HOST,
    }

    r = requests.get(API_URL, headers=headers, params=querystring, timeout=60)
    r.raise_for_status()
    return r.json()
