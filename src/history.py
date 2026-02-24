import csv
from pathlib import Path
from datetime import date

HISTORY_PATH = Path("data/history.csv")


def append_row(
    source: str,
    destination: str,
    currency: str,
    best_price: float | None,
    best_itinerary_id: str | None,
) -> None:
    HISTORY_PATH.parent.mkdir(parents=True, exist_ok=True)

    run_date = date.today().isoformat()

    with HISTORY_PATH.open("a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow([run_date, source, destination, currency, best_price, best_itinerary_id])
