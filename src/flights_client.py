from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict

import requests

from src.config import Config


@dataclass(frozen=True)
class ApiResult:
    status_code: int
    payload: Dict[str, Any]


class FlightsClient:
    def __init__(self, cfg: Config) -> None:
        self.cfg = cfg
        self.session = requests.Session()
        self.session.headers.update(
            {
                "x-rapidapi-key": cfg.rapidapi_key,
                "x-rapidapi-host": cfg.rapidapi_host,
            }
        )

    def search_return(
        self,
        origin: str,
        destination: str,
        departure_date: str,
        return_date: str,
        stops: int = 0,
        adults: int = 1,
        children: int = 0,
        infants: int = 0,
    ) -> ApiResult:
        url = f"{self.cfg.base_url.rstrip('/')}/flights/search-return"
        params = {
            "originSkyId": origin,
            "destinationSkyId": destination,
            "departureDate": departure_date,
            "returnDate": return_date,
            "stops": str(stops),
            "adults": str(adults),
            "children": str(children),
            "infants": str(infants),
        }

        r = self.session.get(url, params=params, timeout=60)

        # Debug on non-200
        if r.status_code != 200:
            print(f"[API-ERROR] status={r.status_code} url={url} params={params}")
            print(f"[API-ERROR] body={r.text[:1000]}")  # first 1000 chars

        try:
            payload = r.json()
        except Exception:
            payload = {"raw": r.text}

        return ApiResult(status_code=r.status_code, payload=payload)
