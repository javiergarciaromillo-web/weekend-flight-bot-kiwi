import json
from src.kiwi_fetch import fetch_round_trip


def main():
    data = fetch_round_trip(
        source="City:amsterdam_nl",
        destination="City:barcelona_es",
        nights=2,
        currency="EUR",
        limit=1,
    )

    itins = data.get("itineraries", [])
    print("itineraries:", len(itins))
    if not itins:
        return

    it0 = itins[0]
    outbound = it0.get("outbound")
    inbound = it0.get("inbound")

    print("outbound keys:", list(outbound.keys()) if isinstance(outbound, dict) else type(outbound))
    print("inbound keys:", list(inbound.keys()) if isinstance(inbound, dict) else type(inbound))

    out_s = json.dumps(outbound, ensure_ascii=False)
    in_s = json.dumps(inbound, ensure_ascii=False)

    print("\nOUTBOUND (first 3000 chars):")
    print(out_s[:3000])

    print("\nINBOUND (first 3000 chars):")
    print(in_s[:3000])


if __name__ == "__main__":
    main()
