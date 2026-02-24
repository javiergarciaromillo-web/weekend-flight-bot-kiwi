from src.kiwi_fetch import test_call


def main():
    data = test_call()
    itineraries = data.get("itineraries", [])
    print("Found itineraries:", len(itineraries))

    if not itineraries:
        return

    price0 = itineraries[0].get("price", {})
    print("price keys:", list(price0.keys()))
    print("price object example:", price0)

    meta = data.get("metadata", {})
    print("metadata keys:", list(meta.keys())[:30])
    print("metadata example (short):", {k: meta.get(k) for k in list(meta.keys())[:10]})


if __name__ == "__main__":
    main()
