from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Tuple


@dataclass(frozen=True)
class Offer:
    price_eur: float
    carrier: str
    flight_out: str
    depart_out: str
    arrive_out: str
    flight_in: str
    depart_in: str
    arrive_in: str
    provider: str


def _parse_iso_local(dt_str: str) -> datetime:
    s = dt_str.replace("Z", "+00:00")
    return datetime.fromisoformat(s)


def _hhmm(dt_str: str) -> str:
    return _parse_iso_local(dt_str).strftime("%H:%M")


def _within(t_hhmm: str, time_from: str, time_to: str) -> bool:
    return time_from <= t_hhmm <= time_to


def _time_ok(
    depart_iso: str,
    arrive_iso: str,
    time_from: str,
    time_to: str,
    mode: str,  # DEPART | ARRIVE | EITHER
) -> bool:
    dep = _hhmm(depart_iso)
    arr = _hhmm(arrive_iso)
    if mode == "DEPART":
        return _within(dep, time_from, time_to)
    if mode == "ARRIVE":
        return _within(arr, time_from, time_to)
    # EITHER
    return _within(dep, time_from, time_to) or _within(arr, time_from, time_to)


def extract_offers_with_stats(
    payload: Dict[str, Any],
    out_from: str,
    out_to: str,
    out_mode: str,
    in_from: str,
    in_to: str,
    in_mode: str,
) -> Tuple[List[Offer], Dict[str, Any]]:
    data = payload.get("data") or {}
    itineraries = data.get("itineraries") or []

    parsed_total = 0
    out_ok = 0
    in_ok = 0
    both_ok = 0

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

            ok_out = _time_ok(out_depart_iso, out_arrive_iso, out_from, out_to, out_mode)
            ok_in = _time_ok(in_depart_iso, in_arrive_iso, in_from, in_to, in_mode)

            if ok_out:
                out_ok += 1
            if ok_in:
                in_ok += 1
            if not (ok_out and ok_in):
                continue

            both_ok += 1

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
        "totalResultCount": payload.get("totalResultCount"),
        "itineraries_len": len(itineraries),
        "parsed_total": parsed_total,
        "out_ok": out_ok,
        "in_ok": in_ok,
        "both_ok": both_ok,
        "examples": examples,
        "out_mode": out_mode,
        "in_mode": in_mode,
    }
    return offers, stats
