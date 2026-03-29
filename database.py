"""
database.py — Single source of truth for DB connection + schema.
"""
import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "database.db")

PRODUCT_NAME = "Samsung Galaxy M34 5G"
MRP = 22999.0  # Fixed MRP in ₹


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Create table if it doesn't exist and seed one row if empty."""
    with get_connection() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS price_history (
                id               INTEGER PRIMARY KEY AUTOINCREMENT,
                product_name     TEXT    NOT NULL,
                price            REAL    NOT NULL,
                mrp              REAL    NOT NULL,
                discount_percent REAL    NOT NULL,
                date             TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        conn.commit()

        count = conn.execute("SELECT COUNT(*) FROM price_history").fetchone()[0]
        if count == 0:
            # Seed 60 days of historical data so charts look great on first run
            import random
            from datetime import datetime, timedelta

            random.seed(42)
            base_price = 19999.0
            today = datetime.now()

            rows = []
            for day_offset in range(59, -1, -1):
                dt = today - timedelta(days=day_offset)
                # Weekend / festival spikes downward
                festival = day_offset in {0, 7, 14, 21, 30, 45, 59}
                if festival:
                    price = round(base_price * random.uniform(0.68, 0.75), 2)
                else:
                    price = round(base_price * random.uniform(0.85, 0.97), 2)
                discount = round((MRP - price) / MRP * 100, 2)
                rows.append((PRODUCT_NAME, price, MRP, discount, dt.strftime("%Y-%m-%d %H:%M:%S")))

            conn.executemany(
                "INSERT INTO price_history (product_name, price, mrp, discount_percent, date) VALUES (?,?,?,?,?)",
                rows,
            )
            conn.commit()
            print(f"[DB] Seeded 60 days of history for '{PRODUCT_NAME}'.")
