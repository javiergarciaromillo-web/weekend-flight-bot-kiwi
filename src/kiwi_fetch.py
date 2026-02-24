import os
import requests

def test_call():
    url = "https://kiwi-com-cheap-flights.p.rapidapi.com/round-trip"

    querystring = {
        "source": "City:amsterdam_nl",
        "destination": "City:barcelona_es",
        "currency": "EUR",
        "locale": "en",
        "adults": "1",
        "children": "0",
        "infants": "0",
        "handbags": "1",
        "holdbags": "0",
        "cabinClass": "ECONOMY",
        "sortBy": "QUALITY",
        "sortOrder": "ASCENDING",
        "transportTypes": "FLIGHT",
        "limit": "5"
    }

    headers = {
        "x-rapidapi-key": os.environ["RAPIDAPI_KEY"],
        "x-rapidapi-host": os.environ["RAPIDAPI_HOST"]
    }

    response = requests.get(url, headers=headers, params=querystring, timeout=30)
    response.raise_for_status()

    return response.json()
