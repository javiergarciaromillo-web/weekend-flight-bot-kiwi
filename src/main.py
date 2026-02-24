from datetime import time

from src.kiwi_fetch import fetch_round_trip
from src.history import append_row
from src.itinerary_extract import extract_leg_flights, itinerary_ok_after


ORIGINS = {
    "AMS": "City:amsterdam_nl",
    "RTM": "City:rotterdam_nl",
}

PATTERNS = {
    "fri_sun": 2,
    "thu_sun": 3,
    "fri_mon": 3,
    "thu_mon": 4,
}

MIN_DEPARTURE_TIME = time(17, 0)  # >= 17:00 local


def pick_best_filtered(itineraries: list[dict]):
    best_price = None
    best_it = None
    best_out_dep = None
    best_in_dep = None

    for it in itineraries:
        amount_str = (it.get("price", {}) or {}).get("amount")
        if not amount_str:
            continue
        try:
            amount = float(amount_str)
        except ValueError:
            continue

        ok, out_dep, in_dep = itinerary_ok_after(it, MIN_DEPARTURE_TIME)
        if not ok:
            continue

        if best_price is None or amount < best_price:
            best_price = amount
            best_it = it
            best_out_dep = out_dep
            best_in_dep = in_dep

    return best_price, best_it, best_out_dep, best_in_dep


def main():
    currency = "EUR"
    destination = "City:barcelona_es"

    for origin_code, origin in ORIGINS.items():
        for pattern_name, nights in PATTERNS.items():
            print(f"\nOrigin: {origin_code} | pattern: {pattern_name} ({nights} nights)")

            data = fetch_round_trip(
                source=origin,
                destination=destination,
                nights=nights,
                currency=currency,
                limit=20,
            )

            itineraries = data.get("itineraries", [])
            print("Found itineraries:", len(itineraries))

            best_price, best_it, out_dep, in_dep = pick_best_filtered(itineraries)

            if not best_it:
                print("Best (>=17:00 local): NONE")
                append_row(
                    origin=origin_code,
                    pattern=pattern_name,
                    destination="BCN",
                    currency=currency,
                    best_price=None,
                    best_itinerary_id=None,
                    out_dep=None,
                    in_dep=None,
                    carriers=None,
                    flight_numbers=None,
                )
                continue

            outbound = best_it.get("outbound") or {}
            inbound = best_it.get("inbound") or {}
            carriers_out, flights_out = extract_leg_flights(outbound)
            carriers_in, flights_in = extract_leg_flights(inbound)

            carriers = ", ".join([x for x in [carriers_out, carriers_in] if x]) or None
            flight_numbers = ", ".join([x for x in [flights_out, flights_in] if x]) or None

            out_dep_s = out_dep.isoformat() if out_dep else None
            in_dep_s = in_dep.isoformat() if in_dep else None

            print("Best (>=17:00 local):", best_price, currency)
            print("  out_dep:", out_dep_s)
            print("  in_dep:", in_dep_s)
            print("  carriers:", carriers)
            print("  flight_numbers:", flight_numbers)

            append_row(
                origin=origin_code,
                pattern=pattern_name,
                destination="BCN",
                currency=currency,
                best_price=best_price,
                best_itinerary_id=best_it.get("id"),
                out_dep=out_dep_s,
                in_dep=in_dep_s,
                carriers=carriers,
                flight_numbers=flight_numbers,
            )


if __name__ == "__main__":
    main()
