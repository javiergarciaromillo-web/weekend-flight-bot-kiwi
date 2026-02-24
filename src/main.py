from src.kiwi_fetch import test_call


def main():
    data = test_call()

    itineraries = data.get("itineraries", [])
    print("Found itineraries:", len(itineraries))

    for i, it in enumerate(itineraries[:5], start=1):
        price = it.get("price", {})
        total = price.get("amount")
        currency = price.get("currency")
        print(f"{i}. Price: {total} {currency}")


if __name__ == "__main__":
    main()
