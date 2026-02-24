from src.kiwi_fetch import fetch_round_trip
from src.history import append_row


PATTERNS = {
    "fri_sun": 2,
    "thu_sun": 3,
    "fri_mon": 3,
    "thu_mon": 4,
}


def get_best(itineraries: list[dict]) -> tuple[float | None, str | None]:
    best_price = None
    best_id = None

    for it in itineraries:
        price_obj = it.get("price", {})
        amount_str = price_obj.get("amount")
        if not amount_str:
            continue

        try:
            amount = float(amount_str)
        except ValueError:
            continue

        if best_price is None or amount < best_price:
            best_price = amount
            best_id = it.get("id")

    return best_price, best_id


def main():
    currency = "EUR"
    source = "City:amsterdam_nl"
    destination = "City:barcelona_es"

    for pattern_name, nights in PATTERNS.items():
        print(f"\nRunning pattern: {pattern_name} ({nights} nights)")

        data = fetch_round_trip(
            source=source,
            destination=destination,
            nights=nights,
            currency=currency,
            limit=20,
        )

        itineraries = data.get("itineraries", [])
        print("Found itineraries:", len(itineraries))

        best_price, best_id = get_best(itineraries)
        print("Best:", best_price, currency)

        append_row(
            source=f"{source}_{pattern_name}",
            destination=destination,
            currency=currency,
            best_price=best_price,
            best_itinerary_id=best_id,
        )


if __name__ == "__main__":
    main()
