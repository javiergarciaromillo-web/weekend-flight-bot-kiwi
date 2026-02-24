from src.kiwi_fetch import fetch_round_trip
from src.report_builder import collect_weekend_report
from src.email_report import build_html_report, send_email


ORIGINS = {
    "AMS": "City:amsterdam_nl",
    "RTM": "City:rotterdam_nl",
}

DESTINATION = "City:barcelona_es"
CURRENCY = "EUR"

# nights=3 cubre Thu->Sun y Fri->Mon (se separa por weekday en el código)
NIGHTS_QUERIES = [2, 3, 4]


def main():
    all_origins_buckets = {}

    for origin_label, origin in ORIGINS.items():
        all_itins = []
        for nights in NIGHTS_QUERIES:
            data = fetch_round_trip(
                source=origin,
                destination=DESTINATION,
                nights=nights,
                currency=CURRENCY,
                limit=200,
            )
            itins = data.get("itineraries", [])
            all_itins.extend(itins)

        buckets = collect_weekend_report(origin_label=origin_label, itineraries=all_itins, currency=CURRENCY)
        all_origins_buckets[origin_label] = buckets

    html = build_html_report(all_origins_buckets)
    send_email(subject="Weekend flight monitor (next 5 weeks)", html_body=html)
    print("Email sent.")


if __name__ == "__main__":
    main()
