import sqlite3
from pathlib import Path


DB = Path("data/prices.db")


def init_db():

    DB.parent.mkdir(exist_ok=True)

    with sqlite3.connect(DB) as conn:

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS prices (
                run_date TEXT,
                origin TEXT,
                outbound TEXT,
                inbound TEXT,
                price REAL
            )
            """
        )


def store_options(run_date, rows):

    with sqlite3.connect(DB) as conn:

        for r in rows:

            conn.execute(
                """
                INSERT INTO prices
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    run_date.isoformat(),
                    r["origin"],
                    r["outbound"].isoformat(),
                    r["inbound"].isoformat(),
                    r["price"],
                ),
            )

        conn.commit()
