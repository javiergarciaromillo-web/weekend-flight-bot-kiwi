from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple


@dataclass(frozen=True)
class Offer:
    price_eur: float
    carrier: str
    flight_out: str
    depart_out: str  # localTime
    arrive_out: str  # localTime
    flight_in: str
    depart_in: str
    arrive_in: str
    provider: str


def _parse_iso_local(dt_str: str) -> datetime:
    # "2026-03-05T21:40:00" or "...Z"
    s = dt_str.replace("Z", "+00:00")
    return datetime.fromisoformat(s)


def _hhmm(dt_str: str) -> str:
    return _parse_iso_local(dt_str).strftime("%H:%M")


def _within_window(dt_str: str, time_from: str, time_to: str) -> bool:
    t = _parse_iso_local(dt_str).strftime("%H:%M")
    return time_from <= t <= time_to


def extract_offers(
    payload: Dict[str, Any],
    time_from: str,
    time_to: str,
) -> List[Offer]:
    data = payload.get("data") or {}
    itineraries = data.get("itineraries") or []
    offers: List[Offer] = []

    for it in itineraries:
        try:
            outbound = it["outbound"]
            inbound = it["inbound"]

            out_seg = outbound["sectorSegments"][0]["segment"]
            in_seg = inbound["sectorSegments"][0]["segment"]

            out_depart = out_seg["source"]["localTime"]
            out_arrive = out_seg["destination"]["localTime"]
            in_depart = in_seg["source"]["localTime"]
            in_arrive = in_seg["destination"]["localTime"]

            # Time window filter on departure times
            if not _within_window(out_depart, time_from, time_to):
                continue
            if not _within_window(in_depart, time_from, time_to):
                continue

            # EUR price (preferred)
            price = it.get("price", {}) or {}
            price_eur = None
            pe = price.get("priceEur", {}) or {}
            if "amount" in pe and pe["amount"] is not None:
                price_eur = float(pe["amount"])
            elif "amount" in price and price["amount"] is not None:
                # fallback: assume it is EUR (best effort)
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
                    depart_out=_hhmm(out_depart),
                    arrive_out=_hhmm(out_arrive),
                    flight_in=flight_in,
                    depart_in=_hhmm(in_depart),
                    arrive_in=_hhmm(in_arrive),
                    provider=provider,
                )
            )
        except Exception:
            # Skip malformed itinerary
            continue

    offers.sort(key=lambda o: o.price_eur)
    return offers
