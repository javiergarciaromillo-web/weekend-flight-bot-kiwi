from __future__ import annotations

import os
import sqlite3
from dataclasses import dataclass
from typing import Optional, Tuple


DB_PATH = os.getenv("DB_PATH", "data/flights.sqlite")


@dataclass(frozen=True)
class Snapshot:
    run_date: str  # YYYY-MM-DD
    origin: str
    destination: str
    pattern: str
    outbound_date: str
    inbound_date: str
    best_price_eur: Optional[float]
    offers_json: str  # json string (top_n offers)
    last_updated: str  # YYYY-MM-DD (when API was refreshed)


def _connect() -> sqlite3.Connection:
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA journal_mode=WAL;")
    return conn


def init_db() -> None:
    conn = _connect()
    try:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS snapshots (
              run_date TEXT NOT NULL,
              origin TEXT NOT NULL,
              destination TEXT NOT NULL,
              pattern TEXT NOT NULL,
              outbound_date TEXT NOT NULL,
              inbound_date TEXT NOT NULL,
              best_price_eur REAL,
              offers_json TEXT NOT NULL,
              last_updated TEXT NOT NULL,
              PRIMARY KEY (run_date, origin, destination, pattern, outbound_date, inbound_date)
            );
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS meta (
              k TEXT PRIMARY KEY,
              v TEXT NOT NULL
            );
            """
        )
        conn.commit()
    finally:
        conn.close()


def set_meta(key: str, value: str) -> None:
    conn = _connect()
    try:
        conn.execute(
            "INSERT INTO meta(k, v) VALUES(?, ?) ON CONFLICT(k) DO UPDATE SET v=excluded.v;",
            (key, value),
        )
        conn.commit()
    finally:
        conn.close()


def get_meta(key: str) -> Optional[str]:
    conn = _connect()
    try:
        cur = conn.execute("SELECT v FROM meta WHERE k = ?;", (key,))
        row = cur.fetchone()
        return row[0] if row else None
    finally:
        conn.close()


def upsert_snapshot(s: Snapshot) -> None:
    conn = _connect()
    try:
        conn.execute(
            """
            INSERT INTO snapshots(
              run_date, origin, destination, pattern, outbound_date, inbound_date,
              best_price_eur, offers_json, last_updated
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(run_date, origin, destination, pattern, outbound_date, inbound_date)
            DO UPDATE SET
              best_price_eur=excluded.best_price_eur,
              offers_json=excluded.offers_json,
              last_updated=excluded.last_updated;
            """,
            (
                s.run_date,
                s.origin,
                s.destination,
                s.pattern,
                s.outbound_date,
                s.inbound_date,
                s.best_price_eur,
                s.offers_json,
                s.last_updated,
            ),
        )
        conn.commit()
    finally:
        conn.close()


def get_previous_best_price(
    origin: str,
    destination: str,
    pattern: str,
    outbound_date: str,
    inbound_date: str,
    run_date: str,
) -> Optional[float]:
    conn = _connect()
    try:
        cur = conn.execute(
            """
            SELECT best_price_eur
            FROM snapshots
            WHERE origin=? AND destination=? AND pattern=? AND outbound_date=? AND inbound_date=?
              AND run_date < ?
            ORDER BY run_date DESC
            LIMIT 1;
            """,
            (origin, destination, pattern, outbound_date, inbound_date, run_date),
        )
        row = cur.fetchone()
        if not row:
            return None
        return row[0]
    finally:
        conn.close()


def get_latest_known_offers(
    origin: str,
    destination: str,
    pattern: str,
    outbound_date: str,
    inbound_date: str,
    run_date: str,
) -> Optional[Tuple[Optional[float], str, str]]:
    """
    Returns (best_price_eur, offers_json, last_updated) from the latest snapshot
    before the current run_date for the same key.
    """
    conn = _connect()
    try:
        cur = conn.execute(
            """
            SELECT best_price_eur, offers_json, last_updated
            FROM snapshots
            WHERE origin=? AND destination=? AND pattern=? AND outbound_date=? AND inbound_date=?
              AND run_date < ?
            ORDER BY run_date DESC
            LIMIT 1;
            """,
            (origin, destination, pattern, outbound_date, inbound_date, run_date),
        )
        row = cur.fetchone()
        if not row:
            return None
        return row[0], row[1], row[2]
    finally:
        conn.close()
