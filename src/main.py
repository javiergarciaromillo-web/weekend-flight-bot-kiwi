from datetime import date, timedelta
from src.kiwi_fetch import fetch_round_trip_window

def _first_time(it, leg_key):
    leg = it.get(leg_key) or {}
    segs = leg.get("sectorSegments") or []
    if not segs:
        return None
    seg = (segs[0] or {}).get("segment") or {}
    return ((seg.get("source") or {}).get("localTime"))

def main():
    start = date.today()
    end = start + timedelta(weeks=5)

    data = fetch_round_trip_window(
        source="City:amsterdam_nl",
        destination="City:barcelona_es",
        start_date=start,
        end_date=end,
        limit=20,
        max_stops=0,
    )

    itins = data.get("itineraries", []) or []
    print("itineraries:", len(itins))
    if itins:
        print("OUT first:", _first_time(itins[0], "outbound"))
        print("IN  first:", _first_time(itins[0], "inbound"))
        print("OUT last :", _first_time(itins[-1], "outbound"))
        print("IN  last :", _first_time(itins[-1], "inbound"))

if __name__ == "__main__":
    main()
