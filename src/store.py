from __future__ import annotations

import sqlite3
from datetime import date
from pathlib import Path
from src.models import FlightOption, HistoricalRow

DB_PATH = Path("data/prices.db")


def init_db() -> None:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS flight_prices (
                run_date TEXT NOT NULL,
                weekend_start TEXT NOT NULL,
                pattern_label TEXT NOT NULL,
                origin TEXT NOT NULL,
                destination TEXT NOT NULL,
                outbound_date TEXT NOT NULL,
                inbound_date TEXT NOT NULL,
                airline TEXT NOT NULL,
                outbound_flight_no TEXT NOT NULL,
                inbound_flight_no TEXT NOT NULL,
                outbound_departure TEXT NOT NULL,
                outbound_arrival TEXT NOT NULL,
                inbound_departure TEXT NOT NULL,
                inbound_arrival TEXT NOT NULL,
                total_price_eur REAL NOT NULL,
                currency TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_prices_lookup
            ON flight_prices (run_date, weekend_start, pattern_label)
            """
        )
        conn.commit()


def store_options(run_date: date, options: list[FlightOption]) -> None:
    if not options:
        return

    with sqlite3.connect(DB_PATH) as conn:
        conn.executemany(
            """
            INSERT INTO flight_prices (
                run_date,
                weekend_start,
                pattern_label,
                origin,
                destination,
                outbound_date,
                inbound_date,
                airline,
                outbound_flight_no,
                inbound_flight_no,
                outbound_departure,
                outbound_arrival,
                inbound_departure,
                inbound_arrival,
                total_price_eur,
                currency
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    run_date.isoformat(),
                    opt.outbound_date.isoformat(),
                    opt.pattern_label,
                    opt.origin,
                    opt.destination,
                    opt.outbound_date.isoformat(),
                    opt.inbound_date.isoformat(),
                    opt.airline,
                    opt.outbound_flight_no,
                    opt.inbound_flight_no,
                    opt.outbound_departure,
                    opt.outbound_arrival,
                    opt.inbound_departure,
                    opt.inbound_arrival,
                    opt.total_price_eur,
                    opt.currency,
                )
                for opt in options
            ],
        )
        conn.commit()


def previous_best_price(run_date: date, weekend_start: date, pattern_label: str) -> float | None:
    with sqlite3.connect(DB_PATH) as conn:
        row = conn.execute(
            """
            SELECT MIN(total_price_eur)
            FROM flight_prices
            WHERE run_date < ?
              AND weekend_start = ?
              AND pattern_label = ?
            ORDER BY run_date DESC
            """,
            (run_date.isoformat(), weekend_start.isoformat(), pattern_label),
        ).fetchone()

    if not row or row[0] is None:
        return None
    return float(row[0])


def historical_best_for_weekend(weekend_start: date) -> list[HistoricalRow]:
    with sqlite3.connect(DB_PATH) as conn:
        rows = conn.execute(
            """
            SELECT run_date, weekend_start, pattern_label, MIN(total_price_eur)
            FROM flight_prices
            WHERE weekend_start = ?
            GROUP BY run_date, weekend_start, pattern_label
            ORDER BY run_date ASC, pattern_label ASC
            """,
            (weekend_start.isoformat(),),
        ).fetchall()

    result: list[HistoricalRow] = []
    for run_date_s, weekend_start_s, pattern_label, price in rows:
        result.append(
            HistoricalRow(
                run_date=date.fromisoformat(run_date_s),
                weekend_start=date.fromisoformat(weekend_start_s),
                pattern_label=pattern_label,
                best_price_eur=float(price),
            )
        )
    return result
