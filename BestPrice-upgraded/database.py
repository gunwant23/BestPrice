"""
database.py — DB connection, schema, and seeding.
Supports multiple products; uses config.py as the single source of truth.
"""
from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta
from pathlib import Path
from typing import Generator, Optional

from config import DB_PATH, PRODUCTS, Product


# ── Connection ────────────────────────────────────────────────────────────────
@contextmanager
def get_connection() -> Generator[sqlite3.Connection, None, None]:
    """Thread-safe context manager that always closes the connection."""
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")   # better concurrent reads
    conn.execute("PRAGMA foreign_keys=ON")
    try:
        yield conn
    finally:
        conn.close()


# ── Schema ────────────────────────────────────────────────────────────────────
_CREATE_TABLE = """
CREATE TABLE IF NOT EXISTS price_history (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    product_slug     TEXT    NOT NULL,
    product_name     TEXT    NOT NULL,
    price            REAL    NOT NULL    CHECK(price > 0),
    mrp              REAL    NOT NULL    CHECK(mrp > 0),
    discount_percent REAL    NOT NULL,
    date             TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);
"""

_CREATE_INDEXES = [
    "CREATE INDEX IF NOT EXISTS idx_product_date ON price_history (product_slug, date);",
    "CREATE INDEX IF NOT EXISTS idx_date         ON price_history (date);",
]


def init_db() -> None:
    """Create tables and indexes; seed demo data if the table is empty."""
    with get_connection() as conn:
        conn.execute(_CREATE_TABLE)
        for idx in _CREATE_INDEXES:
            conn.execute(idx)
        conn.commit()

        count = conn.execute("SELECT COUNT(*) FROM price_history").fetchone()[0]
        if count == 0:
            _seed_all_products(conn)


# ── Seeding ───────────────────────────────────────────────────────────────────
def _seed_all_products(conn: sqlite3.Connection) -> None:
    """Insert 60 days of realistic synthetic history for every product."""
    import random

    today = datetime.now()
    rows  = []

    for slug, product in PRODUCTS.items():
        random.seed(hash(slug) & 0xFFFF)           # deterministic per product
        base = product.mrp * 0.88                  # typical street price

        for day_offset in range(59, -1, -1):
            dt = today - timedelta(days=day_offset)
            festival = day_offset in {0, 7, 14, 21, 30, 45, 59}
            if festival:
                price = round(base * random.uniform(0.68, 0.76), 2)
            else:
                price = round(base * random.uniform(0.84, 0.97), 2)

            price    = max(product.mrp * 0.55, min(product.mrp * 0.98, price))
            discount = round((product.mrp - price) / product.mrp * 100, 2)
            rows.append((
                slug, product.name, price, product.mrp, discount,
                dt.strftime("%Y-%m-%d %H:%M:%S"),
            ))

    conn.executemany(
        """INSERT INTO price_history
           (product_slug, product_name, price, mrp, discount_percent, date)
           VALUES (?,?,?,?,?,?)""",
        rows,
    )
    conn.commit()
    print(f"[DB] Seeded {len(rows)} rows across {len(PRODUCTS)} products.")


# ── Queries ───────────────────────────────────────────────────────────────────
def insert_price(slug: str, product: Product, price: float) -> float:
    """Insert a new price record; return the computed discount."""
    discount = round((product.mrp - price) / product.mrp * 100, 2)
    with get_connection() as conn:
        conn.execute(
            """INSERT INTO price_history
               (product_slug, product_name, price, mrp, discount_percent, date)
               VALUES (?,?,?,?,?,?)""",
            (slug, product.name, price, product.mrp, discount,
             datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        )
        conn.commit()
    return discount


def get_last_price(slug: str) -> Optional[float]:
    """Return the most recent recorded price for *slug*, or None."""
    with get_connection() as conn:
        row = conn.execute(
            "SELECT price FROM price_history WHERE product_slug=? ORDER BY date DESC LIMIT 1",
            (slug,),
        ).fetchone()
    return row["price"] if row else None


if __name__ == "__main__":
    init_db()
    print("Database initialised successfully.")
