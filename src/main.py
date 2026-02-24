from datetime import date, timedelta
import json

from src.flights_fetch import search_return


def main():
    today = date.today()
    end = today + timedelta(weeks=5)

    data = search_return(
        origin_sky_id="AMS",
        destination_sky_id="BCN",
        departure_start=today,
        departure_end=end,
        return_start=today,
        return_end=end,
        limit=5,
        stops=0,
        currency="EUR",
        locale="en-US",
        market="US",
        sort="PRICE",
        outbound_departure_times="17,24",
        inbound_departure_times="17,24",
    )

    print("Top-level keys:", list(data.keys()))
    s = json.dumps(data, ensure_ascii=False)
    print("JSON first 2500 chars:")
    print(s[:2500])


if __name__ == "__main__":
    main()
