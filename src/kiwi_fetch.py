import os
import requests

def test_call():
    url = "REPLACE_WITH_RAPIDAPI_URL"
    params = {}
    headers = {
        "X-RapidAPI-Key": os.environ["RAPIDAPI_KEY"],
        "X-RapidAPI-Host": os.environ["RAPIDAPI_HOST"],
    }
    r = requests.get(url, headers=headers, params=params, timeout=30)
    r.raise_for_status()
    return r.json()
