from __future__ import annotations

import sqlite3
from pathlib import Path


DB = Path("data/prices.db")


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
                    raw_text
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                ),
            )
        conn.commit()
