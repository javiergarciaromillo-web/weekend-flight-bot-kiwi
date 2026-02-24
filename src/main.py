from datetime import time

from src.kiwi_fetch import fetch_round_trip
from src.history import append_row
from src.itinerary_extract import extract_itinerary_summary, leg_ok_after


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


def get_best_after_17(itineraries: list[dict]):
    best_price = None
    best_it = None
    best_summary = None

    for it in itineraries:
        # price
        amount_str = (it.get("price", {}) or {}).get("amount")
        if not amount_str:
            continue
        try:
            amount = float(amount_str)
        except ValueError:
            continue

        # time filter (best-effort)
        outbound = it.get("outbound", {})
        inbound = it.get("inbound", {})

        ok_out, _ = leg_ok_after(outbound, MIN_DEPARTURE_TIME)
        ok_in, _ = leg_ok_after(inbound, MIN_DEPARTURE_TIME)
        if not (ok_out and ok_in):
            continue

        if best_price is None or amount < best_price:
            best_price = amount
            best_it = it
            best_summary = extract_itinerary_summary(it)

    return best_price, best_it, best_summary


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

            best_price, best_it, summary = get_best_after_17(itineraries)

            if best_it is None:
                print("Best (>=17:00): NONE")
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

            out_dep = summary["out_dep"].isoformat() if summary and summary["out_dep"] else None
            in_dep = summary["in_dep"].isoformat() if summary and summary["in_dep"] else None
            carriers = summary.get("carriers") if summary else None
            flight_numbers = summary.get("flight_numbers") if summary else None

            print("Best (>=17:00):", best_price, currency)
            print("  out_dep:", out_dep)
            print("  in_dep:", in_dep)
            print("  carriers:", carriers)
            print("  flight_numbers:", flight_numbers)

            append_row(
                origin=origin_code,
                pattern=pattern_name,
                destination="BCN",
                currency=currency,
                best_price=best_price,
                best_itinerary_id=best_it.get("id"),
                out_dep=out_dep,
                in_dep=in_dep,
                carriers=carriers,
                flight_numbers=flight_numbers,
            )


if __name__ == "__main__":
    main()
