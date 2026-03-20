from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any


DB = Path("data/prices.db")


def _get_columns(conn: sqlite3.Connection, table_name: str) -> set[str]:
    rows = conn.execute(f"PRAGMA table_info({table_name})").fetchall()
    return {row[1] for row in rows}


def init_db() -> None:
    DB.parent.mkdir(exist_ok=True)

    with sqlite3.connect(DB) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS prices (
                run_date TEXT NOT NULL,
                origin TEXT NOT NULL,
                destination TEXT NOT NULL,
                outbound TEXT NOT NULL,
                inbound TEXT NOT NULL,
                airline TEXT,
                outbound_departure TEXT,
                outbound_arrival TEXT,
                inbound_departure TEXT,
                inbound_arrival TEXT,
                outbound_flight_no TEXT,
                inbound_flight_no TEXT,
                price REAL NOT NULL,
                source_url TEXT,
                page_title TEXT,
                raw_text TEXT
            )
            """
        )

        columns = _get_columns(conn, "prices")

        if "leg_type" not in columns:
            conn.execute("ALTER TABLE prices ADD COLUMN leg_type TEXT")

        if "leg_date" not in columns:
            conn.execute("ALTER TABLE prices ADD COLUMN leg_date TEXT")

        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_prices_weekend
            ON prices (run_date, outbound, inbound, leg_type, origin, destination)
            """
        )

        conn.commit()


def store_options(run_date, rows) -> None:
    with sqlite3.connect(DB) as conn:
        for r in rows:
            conn.execute(
                """
                INSERT INTO prices (
                    run_date,
                    origin,
                    destination,
                    outbound,
                    inbound,
                    airline,
                    outbound_departure,
                    outbound_arrival,
                    inbound_departure,
                    inbound_arrival,
                    outbound_flight_no,
                    inbound_flight_no,
                    price,
                    source_url,
                    page_title,
                    raw_text,
                    leg_type,
                    leg_date
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    run_date.isoformat(),
                    r["origin"],
                    r["destination"],
                    r["outbound"].isoformat(),
                    r["inbound"].isoformat(),
                    r.get("airline"),
                    r.get("outbound_departure"),
                    r.get("outbound_arrival"),
                    r.get("inbound_departure"),
                    r.get("inbound_arrival"),
                    r.get("outbound_flight_no"),
                    r.get("inbound_flight_no"),
                    r["price"],
                    r.get("source_url"),
                    r.get("page_title"),
                    r.get("raw_text"),
                    r.get("leg_type"),
                    r.get("leg_date").isoformat() if r.get("leg_date") else None,
                ),
            )
        conn.commit()


def get_weekend_history(outbound_date, inbound_date) -> list[dict[str, Any]]:
    """
    Returns one row per run_date with:
    - best outbound
    - best inbound
    - best combo
    for the requested weekend block.
    """

    with sqlite3.connect(DB) as conn:
        rows = conn.execute(
            """
            WITH outbound_best AS (
                SELECT
                    run_date,
                    MIN(price) AS best_outbound
                FROM prices
                WHERE outbound = ?
                  AND inbound = ?
                  AND leg_type = 'outbound'
                GROUP BY run_date
            ),
            inbound_best AS (
                SELECT
                    run_date,
                    MIN(price) AS best_inbound
                FROM prices
                WHERE outbound = ?
                  AND inbound = ?
                  AND leg_type = 'inbound'
                GROUP BY run_date
            ),
            merged AS (
                SELECT
                    COALESCE(o.run_date, i.run_date) AS run_date,
                    o.best_outbound,
                    i.best_inbound
                FROM outbound_best o
                LEFT JOIN inbound_best i
                  ON o.run_date = i.run_date

                UNION

                SELECT
                    COALESCE(o.run_date, i.run_date) AS run_date,
                    o.best_outbound,
                    i.best_inbound
                FROM inbound_best i
                LEFT JOIN outbound_best o
                  ON o.run_date = i.run_date
            )
            SELECT
                run_date,
                best_outbound,
                best_inbound,
                CASE
                    WHEN best_outbound IS NOT NULL AND best_inbound IS NOT NULL
                    THEN best_outbound + best_inbound
                    ELSE NULL
                END AS best_combo
            FROM merged
            ORDER BY run_date ASC
            """,
            (
                outbound_date.isoformat(),
                inbound_date.isoformat(),
                outbound_date.isoformat(),
                inbound_date.isoformat(),
            ),
        ).fetchall()

    result: list[dict[str, Any]] = []

    for run_date, best_outbound, best_inbound, best_combo in rows:
        result.append(
            {
                "run_date": run_date,
                "best_outbound": float(best_outbound) if best_outbound is not None else None,
                "best_inbound": float(best_inbound) if best_inbound is not None else None,
                "best_combo": float(best_combo) if best_combo is not None else None,
            }
        )

    return result
