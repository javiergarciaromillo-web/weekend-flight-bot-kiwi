from __future__ import annotations

import sqlite3
from pathlib import Path


DB_PATH = Path("data/prices.db")


def get_conn():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    return sqlite3.connect(DB_PATH)


def _columns(cur, table_name: str) -> set[str]:
    cur.execute(f"PRAGMA table_info({table_name})")
    return {row[1] for row in cur.fetchall()}


def init_db():
    conn = get_conn()
    cur = conn.cursor()

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS weekend_prices (
            run_date TEXT,
            outbound TEXT,
            inbound TEXT,
            best_outbound REAL,
            best_inbound REAL,
            best_combo REAL
        )
        """
    )

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS learning_prices (
            run_date TEXT,
            sample_name TEXT,
            outbound TEXT,
            inbound TEXT,
            days_to_departure INTEGER,
            pattern TEXT,
            best_outbound REAL,
            best_inbound REAL,
            best_combo REAL
        )
        """
    )

    cols = _columns(cur, "learning_prices")

    extra_cols = {
        "outbound_origin": "TEXT",
        "outbound_destination": "TEXT",
        "outbound_airline": "TEXT",
        "outbound_departure_time": "TEXT",
        "outbound_arrival_time": "TEXT",
        "outbound_source_url": "TEXT",
        "inbound_origin": "TEXT",
        "inbound_destination": "TEXT",
        "inbound_airline": "TEXT",
        "inbound_departure_time": "TEXT",
        "inbound_arrival_time": "TEXT",
        "inbound_source_url": "TEXT",
    }

    for col, col_type in extra_cols.items():
        if col not in cols:
            cur.execute(f"ALTER TABLE learning_prices ADD COLUMN {col} {col_type}")

    conn.commit()
    conn.close()
    init_decision_tables()


def save_weekend_snapshot(
    run_date,
    outbound,
    inbound,
    best_outbound,
    best_inbound,
    best_combo,
):
    conn = get_conn()
    cur = conn.cursor()

    cur.execute(
        "DELETE FROM weekend_prices WHERE run_date = ? AND outbound = ? AND inbound = ?",
        (str(run_date), str(outbound), str(inbound)),
    )
    cur.execute(
        """
        INSERT INTO weekend_prices VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            str(run_date),
            str(outbound),
            str(inbound),
            best_outbound,
            best_inbound,
            best_combo,
        ),
    )

    conn.commit()
    conn.close()


def save_learning_snapshot(
    run_date,
    sample_name,
    outbound,
    inbound,
    days_to_departure,
    pattern,
    best_outbound,
    best_inbound,
    best_combo,
    outbound_origin=None,
    outbound_destination=None,
    outbound_airline=None,
    outbound_departure_time=None,
    outbound_arrival_time=None,
    outbound_source_url=None,
    inbound_origin=None,
    inbound_destination=None,
    inbound_airline=None,
    inbound_departure_time=None,
    inbound_arrival_time=None,
    inbound_source_url=None,
):
    conn = get_conn()
    cur = conn.cursor()

    cur.execute(
        "DELETE FROM learning_prices WHERE run_date = ? AND sample_name = ?",
        (str(run_date), sample_name),
    )
    cur.execute(
        """
        INSERT INTO learning_prices (
            run_date,
            sample_name,
            outbound,
            inbound,
            days_to_departure,
            pattern,
            best_outbound,
            best_inbound,
            best_combo,
            outbound_origin,
            outbound_destination,
            outbound_airline,
            outbound_departure_time,
            outbound_arrival_time,
            outbound_source_url,
            inbound_origin,
            inbound_destination,
            inbound_airline,
            inbound_departure_time,
            inbound_arrival_time,
            inbound_source_url
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            str(run_date),
            sample_name,
            str(outbound),
            str(inbound),
            days_to_departure,
            pattern,
            best_outbound,
            best_inbound,
            best_combo,
            outbound_origin,
            outbound_destination,
            outbound_airline,
            outbound_departure_time,
            outbound_arrival_time,
            outbound_source_url,
            inbound_origin,
            inbound_destination,
            inbound_airline,
            inbound_departure_time,
            inbound_arrival_time,
            inbound_source_url,
        ),
    )

    conn.commit()
    conn.close()


def get_weekend_history(outbound, inbound):
    conn = get_conn()
    cur = conn.cursor()

    cur.execute(
        """
        SELECT run_date, best_outbound, best_inbound, best_combo
        FROM weekend_prices
        WHERE outbound = ? AND inbound = ?
        ORDER BY run_date
        """,
        (str(outbound), str(inbound)),
    )

    rows = cur.fetchall()
    conn.close()

    return [
        {
            "run_date": r[0],
            "best_outbound": r[1],
            "best_inbound": r[2],
            "best_combo": r[3],
        }
        for r in rows
    ]


def get_latest_learning_opportunities(limit: int = 10):
    conn = get_conn()
    cur = conn.cursor()

    cur.execute(
        """
        SELECT
            run_date,
            sample_name,
            outbound,
            inbound,
            days_to_departure,
            pattern,
            best_outbound,
            best_inbound,
            best_combo,
            outbound_origin,
            outbound_destination,
            outbound_airline,
            outbound_departure_time,
            outbound_arrival_time,
            outbound_source_url,
            inbound_origin,
            inbound_destination,
            inbound_airline,
            inbound_departure_time,
            inbound_arrival_time,
            inbound_source_url
        FROM learning_prices
        WHERE run_date = (SELECT MAX(run_date) FROM learning_prices)
          AND best_combo IS NOT NULL
        ORDER BY best_combo ASC
        LIMIT ?
        """,
        (limit,),
    )

    rows = cur.fetchall()
    conn.close()

    return [
        {
            "run_date": r[0],
            "sample_name": r[1],
            "outbound": r[2],
            "inbound": r[3],
            "days_to_departure": r[4],
            "pattern": r[5],
            "best_outbound": r[6],
            "best_inbound": r[7],
            "best_combo": r[8],
            "outbound_origin": r[9],
            "outbound_destination": r[10],
            "outbound_airline": r[11],
            "outbound_departure_time": r[12],
            "outbound_arrival_time": r[13],
            "outbound_source_url": r[14],
            "inbound_origin": r[15],
            "inbound_destination": r[16],
            "inbound_airline": r[17],
            "inbound_departure_time": r[18],
            "inbound_arrival_time": r[19],
            "inbound_source_url": r[20],
        }
        for r in rows
    ]


def get_learning_stats(days_to_departure: int, pattern: str):
    conn = get_conn()
    cur = conn.cursor()

    cur.execute(
        """
        SELECT best_combo
        FROM learning_prices
        WHERE pattern = ?
          AND days_to_departure BETWEEN ? AND ?
          AND best_combo IS NOT NULL
        """,
        (
            pattern,
            max(0, days_to_departure - 10),
            days_to_departure + 10,
        ),
    )

    rows = [r[0] for r in cur.fetchall()]
    conn.close()

    if not rows:
        return {
            "count": 0,
            "avg_combo": None,
            "min_combo": None,
        }

    return {
        "count": len(rows),
        "avg_combo": sum(rows) / len(rows),
        "min_combo": min(rows),
    }


# Detailed observations are separate from legacy cheapest-combination history.
# Identity is a timetable proxy: the provider currently returns no flight number.
def init_decision_tables():
    with get_conn() as conn:
        conn.executescript('''
        CREATE TABLE IF NOT EXISTS flight_observations (
            run_date TEXT, filter_version TEXT, leg_date TEXT, origin TEXT,
            destination TEXT, airline TEXT, departure TEXT, arrival TEXT,
            price REAL, source_url TEXT,
            PRIMARY KEY (run_date, filter_version, leg_date, origin, destination,
                         airline, departure, arrival)
        );
        CREATE TABLE IF NOT EXISTS query_observations (
            run_date TEXT, filter_version TEXT, leg_date TEXT, origin TEXT,
            destination TEXT, status TEXT,
            PRIMARY KEY (run_date, filter_version, leg_date, origin, destination)
        );
        CREATE TABLE IF NOT EXISTS booking_decisions (
            run_date TEXT, filter_version TEXT, outbound TEXT, inbound TEXT,
            price REAL, coverage_complete INTEGER, holiday INTEGER, decision_json TEXT,
            PRIMARY KEY (run_date, filter_version, outbound, inbound)
        );
        ''')


def save_flight_observations(run_date, rows, diagnostics):
    from datetime import datetime
    from src.decisions import FILTER_VERSION
    def normalize_time(value):
        value = value or ''
        suffix = '+1' if '+1' in value else ''
        for fmt in ('%I:%M %p', '%H:%M'):
            try:
                return datetime.strptime(value.replace('+1', '').strip().upper(), fmt).strftime('%H:%M') + suffix
            except ValueError:
                pass
        return value
    # Duplicate legs are repeated across date pairs; count each once per day.
    unique = {}
    for row in rows:
        day = str(row.get('leg_date') or row['outbound' if row['leg_type'] == 'outbound' else 'inbound'])
        key = (str(run_date), FILTER_VERSION, day, row['origin'], row['destination'],
               row.get('airline', ''), normalize_time(row.get('outbound_departure')),
               normalize_time(row.get('outbound_arrival')))
        if key not in unique or row['price'] < unique[key][0]:
            unique[key] = (row['price'], row.get('source_url', ''))
    with get_conn() as conn:
        # Replace queried scopes so same-day retries do not retain vanished options.
        scopes = {(str(day), o, d) for o, d, day in diagnostics}
        scopes.update((k[2], k[3], k[4]) for k in unique)
        for day, origin, destination in scopes:
            conn.execute('DELETE FROM flight_observations WHERE run_date=? AND filter_version=? AND leg_date=? AND origin=? AND destination=?',
                         (str(run_date), FILTER_VERSION, day, origin, destination))
        conn.executemany('INSERT OR REPLACE INTO flight_observations VALUES (?,?,?,?,?,?,?,?,?,?)',
                         [key + value for key, value in unique.items()])
        conn.executemany('INSERT OR REPLACE INTO query_observations VALUES (?,?,?,?,?,?)',
                         [(str(run_date), FILTER_VERSION, str(day), o, d, status)
                          for (o, d, day), status in diagnostics.items()])


def get_decision_history(outbound, inbound):
    from src.decisions import FILTER_VERSION
    with get_conn() as conn:
        rows = conn.execute('SELECT run_date, price, coverage_complete, filter_version FROM booking_decisions WHERE outbound=? AND inbound=? AND filter_version=? ORDER BY run_date',
                            (str(outbound), str(inbound), FILTER_VERSION)).fetchall()
    return [dict(run_date=r[0], price=r[1], coverage_complete=bool(r[2]), filter_version=r[3]) for r in rows]


def record_booking_decisions(run_date, rows, pairs, diagnostics):
    import json
    from src.decisions import recommend, FILTER_VERSION
    from src.holidays import holiday_dates
    decisions = {}
    for outbound, inbound in pairs:
        selected = [r for r in rows if (r['outbound'], r['inbound']) == (outbound, inbound)]
        out = [r['price'] for r in selected if r['leg_type'] == 'outbound']
        inc = [r['price'] for r in selected if r['leg_type'] == 'inbound']
        price = min(out) + min(inc) if out and inc else None
        keys = [(a, 'BCN', outbound) for a in ('AMS', 'RTM')] + [('BCN', a, inbound) for a in ('AMS', 'RTM')]
        complete = all(diagnostics.get(key) in ('ok', 'filtered_empty') for key in keys)
        holiday = bool(holiday_dates(outbound, inbound))
        decision = recommend(run_date, outbound, price, get_decision_history(outbound, inbound),
                             holiday=holiday, coverage_complete=complete)
        decisions[(outbound, inbound)] = decision
        with get_conn() as conn:
            conn.execute('INSERT OR REPLACE INTO booking_decisions VALUES (?,?,?,?,?,?,?,?)',
                         (str(run_date), FILTER_VERSION, str(outbound), str(inbound), price,
                          int(complete), int(holiday), json.dumps(decision, ensure_ascii=False)))
    return decisions


def get_horizon_tracking(saturdays, since=None):
    """Latest actually observed fare for each target family weekend.

    Weekly remote checks can be several days old. An unpriced or failed latest
    check must never be replaced by an older price and passed off as current.
    """
    from datetime import date, timedelta
    from src.family import weekend_of
    from src.planner import FILTER_HISTORY_START

    start = str(since or FILTER_HISTORY_START)
    if not saturdays:
        return []
    first = min(saturdays) - timedelta(days=7)
    last = max(saturdays)
    with get_conn() as conn:
        observations = conn.execute(
            """SELECT run_date, outbound, inbound, best_combo
               FROM weekend_prices
               WHERE run_date >= ? AND outbound >= ? AND outbound <= ?
               ORDER BY run_date DESC""",
            (start, str(first), str(last)),
        ).fetchall()
    result = {sat: {'weekend': sat, 'checked_at': None, 'best_price': None,
                    'outbound': None, 'inbound': None} for sat in saturdays}
    for run_day, out_str, inc_str, fare in observations:
        out, inc = date.fromisoformat(out_str), date.fromisoformat(inc_str)
        sat = weekend_of(out)
        if sat not in result or not out <= sat < inc:
            continue
        item = result[sat]
        if item['checked_at'] is None:
            item['checked_at'] = run_day
        if item['checked_at'] == run_day and fare is not None:
            if item['best_price'] is None or fare < item['best_price']:
                item.update(best_price=fare, outbound=out, inbound=inc)
    return [result[sat] for sat in sorted(result)]
