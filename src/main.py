from src.kiwi_fetch import test_call


def main():
    data = test_call()
    itineraries = data.get("itineraries", [])
    print("Found itineraries:", len(itineraries))

    currency = "EUR"  # porque en kiwi_fetch.py estás pasando currency=EUR

    for i, it in enumerate(itineraries[:5], start=1):
        price = it.get("price", {})
        amount_str = price.get("amount")
        amount = float(amount_str) if amount_str is not None else None
        print(f"{i}. Price: {amount} {currency}")


if __name__ == "__main__":
    main()
