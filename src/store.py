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
