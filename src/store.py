from __future__ import annotations

import sqlite3
from pathlib import Path


DB_PATH = Path("data/prices.db")


def get_conn():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    return sqlite3.connect(DB_PATH)


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
):
    conn = get_conn()
    cur = conn.cursor()

    cur.execute(
        """
        INSERT INTO learning_prices VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
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
