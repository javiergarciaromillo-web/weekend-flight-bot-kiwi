import os
import requests
from datetime import date

API_HOST = "flights-scraper-real-time.p.rapidapi.com"


def search_return(
    origin_sky_id: str,
    destination_sky_id: str,
    departure_start: date,
    departure_end: date,
    return_start: date,
    return_end: date,
    *,
    limit: int = 20,
    stops: int = 0,
    adults: int = 1,
    currency: str = "EUR",
    locale: str = "en-US",
    market: str = "US",
    sort: str = "PRICE",
    cabin_class: str = "ECONOMY",
    outbound_departure_times: str = "17,24",
    inbound_departure_times: str = "17,24",
) -> dict:
    url = f"https://{API_HOST}/flights/search-return"

    params = {
        "originSkyId": origin_sky_id,
        "destinationSkyId": destination_sky_id,
        "departureDate": departure_start.isoformat(),
        "departureDateEnd": departure_end.isoformat(),
        "returnDate": return_start.isoformat(),
        "returnDateEnd": return_end.isoformat(),
        "limit": str(limit),
        "stops": str(stops),
        "adults": str(adults),
        "currency": currency,
        "locale": locale,
        "market": market,
        "sort": sort,
        "cabinClass": cabin_class,
        "outboundDepartureTimes": outbound_departure_times,
        "inboundDepartureTimes": inbound_departure_times,
    }

    headers = {
        "x-rapidapi-key": os.environ["RAPIDAPI_KEY"],
        "x-rapidapi-host": API_HOST,
    }

    r = requests.get(url, headers=headers, params=params, timeout=60)
    r.raise_for_status()
    return r.json()
