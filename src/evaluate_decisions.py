"""Read-only offline evaluation: python -m src.evaluate_decisions [database]."""
import json
import sqlite3
import sys
from pathlib import Path
from src.decisions import backtest


def main():
    path = Path(sys.argv[1] if len(sys.argv) > 1 else 'data/prices.db').resolve()
    with sqlite3.connect(path.as_uri() + '?mode=ro', uri=True) as conn:
        conn.row_factory = sqlite3.Row
        rows = [dict(row) for row in conn.execute('SELECT * FROM booking_decisions')]
    outcomes = backtest(rows)
    print(json.dumps(dict(evaluated_trips=len(outcomes), outcomes=outcomes,
                          warning='Descriptive results on observed dates only; overlapping trips are not independent. '
                                  'Missing searches and disappearing flights prevent claims of an optimal window.'), indent=2))


if __name__ == '__main__':
    main()
