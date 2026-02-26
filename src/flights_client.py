from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional

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
        departure_date: str,  # YYYY-MM-DD
        return_date: str,     # YYYY-MM-DD
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
        try:
            payload = r.json()
        except Exception:
            payload = {"status": False, "status_code": r.status_code, "raw": r.text}
        return ApiResult(status_code=r.status_code, payload=payload)
