from src.kiwi_fetch import fetch_round_trip
from src.history import append_row


def get_best(itineraries: list[dict]) -> tuple[float | None, str | None]:
    best_price = None
    best_id = None

    for it in itineraries:
        price_obj = it.get("price", {})
        amount_str = price_obj.get("amount")
        if amount_str is None:
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

    data = fetch_round_trip(source=source, destination=destination, currency=currency, limit=20)
    itineraries = data.get("itineraries", [])
    print("Found itineraries:", len(itineraries))

    best_price, best_id = get_best(itineraries)
    print("Best:", best_price, currency, "id:", best_id)

    append_row(
        source=source,
        destination=destination,
        currency=currency,
        best_price=best_price,
        best_itinerary_id=best_id,
    )
    print("Appended to data/history.csv")


if __name__ == "__main__":
    main()
