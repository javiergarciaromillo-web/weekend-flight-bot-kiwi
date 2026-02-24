import json
from src.kiwi_fetch import fetch_round_trip

def main():
    data = fetch_round_trip(
        source="City:amsterdam_nl",
        destination="City:barcelona_es",
        nights=2,
        currency="EUR",
        limit=3,
    )

    itins = data.get("itineraries", [])
    print("itineraries:", len(itins))
    if not itins:
        return

    it0 = itins[0]
    print("itinerary top keys:", list(it0.keys()))

    # imprime el JSON pero recortado
    s = json.dumps(it0, ensure_ascii=False)
    print("itinerary json (first 2500 chars):")
    print(s[:2500])

if __name__ == "__main__":
    main()
