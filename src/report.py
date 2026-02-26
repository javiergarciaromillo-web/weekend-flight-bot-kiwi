from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Tuple


@dataclass(frozen=True)
class Offer:
    price_eur: float
    carrier: str
    flight_out: str
    depart_out: str  # HH:MM
    arrive_out: str  # HH:MM
    flight_in: str
    depart_in: str
    arrive_in: str
    provider: str


def _parse_iso_local(dt_str: str) -> datetime:
    # accepts "2026-03-05T21:40:00" and "2026-03-05T20:40:00Z"
    s = dt_str.replace("Z", "+00:00")
    return datetime.fromisoformat(s)


def _hhmm(dt_str: str) -> str:
    return _parse_iso_local(dt_str).strftime("%H:%M")


def _within_window(dt_str: str, time_from: str, time_to: str) -> bool:
    t = _hhmm(dt_str)
    return time_from <= t <= time_to


def extract_offers_with_stats(
    payload: Dict[str, Any],
    time_from: str,
    time_to: str,
) -> Tuple[List[Offer], Dict[str, Any]]:
    """
    Parse offers from the flights-scraper-real-time /flights/search-return response.

    Returns:
      - filtered offers (sorted by EUR price asc)
      - stats for troubleshooting (counts + example departure/arrival times)
    """
    data = payload.get("data") or {}
    itineraries = data.get("itineraries") or []

    parsed_total = 0
    time_ok = 0
    offers: List[Offer] = []
    examples: List[Dict[str, str]] = []

    for it in itineraries:
        try:
            outbound = it["outbound"]
            inbound = it["inbound"]

            out_seg = outbound["sectorSegments"][0]["segment"]
            in_seg = inbound["sectorSegments"][0]["segment"]

            out_depart_iso = out_seg["source"]["localTime"]
            out_arrive_iso = out_seg["destination"]["localTime"]
            in_depart_iso = in_seg["source"]["localTime"]
            in_arrive_iso = in_seg["destination"]["localTime"]

            parsed_total += 1

            if len(examples) < 2:
                examples.append(
                    {
                        "out_depart": _hhmm(out_depart_iso),
                        "out_arrive": _hhmm(out_arrive_iso),
                        "in_depart": _hhmm(in_depart_iso),
                        "in_arrive": _hhmm(in_arrive_iso),
                    }
                )

            if not _within_window(out_depart_iso, time_from, time_to):
                continue
            if not _within_window(in_depart_iso, time_from, time_to):
                continue

            time_ok += 1

            price = it.get("price") or {}
            pe = price.get("priceEur") or {}

            if pe.get("amount") is not None:
                price_eur = float(pe["amount"])
            elif price.get("amount") is not None:
                price_eur = float(price["amount"])
            else:
                continue

            carrier = (out_seg.get("carrier") or {}).get("code") or "??"
            flight_out = f"{carrier}{out_seg.get('code', '')}"
            flight_in = f"{carrier}{in_seg.get('code', '')}"
            provider = ((it.get("provider") or {}).get("name")) or "Unknown"

            offers.append(
                Offer(
                    price_eur=price_eur,
                    carrier=carrier,
                    flight_out=flight_out,
                    depart_out=_hhmm(out_depart_iso),
                    arrive_out=_hhmm(out_arrive_iso),
                    flight_in=flight_in,
                    depart_in=_hhmm(in_depart_iso),
                    arrive_in=_hhmm(in_arrive_iso),
                    provider=provider,
                )
            )
        except Exception:
            continue

    offers.sort(key=lambda o: o.price_eur)

    stats = {
        "status": payload.get("status"),
        "status_code": payload.get("status_code"),
        "totalResultCount": payload.get("totalResultCount"),
        "itineraries_len": len(itineraries),
        "parsed_total": parsed_total,
        "time_ok": time_ok,
        "examples": examples,
    }
    return offers, stats
