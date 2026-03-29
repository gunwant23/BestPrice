"""
update_price.py
---------------
Simulates a daily price update for the tracked product.
Run manually or via cron / GitHub Actions every 24 hours.

Cron (local):
    0 0 * * * cd /path/to/BestPrice && python update_price.py

GitHub Actions: see .github/workflows/update_price.yml
"""
import random
import sqlite3
from datetime import datetime

from database import get_connection, init_db, MRP, PRODUCT_NAME


def get_last_price(conn: sqlite3.Connection) -> float:
    row = conn.execute(
        "SELECT price FROM price_history ORDER BY date DESC LIMIT 1"
    ).fetchone()
    # If no history, start at 90% of MRP
    return row["price"] if row else round(MRP * 0.90, 2)


def generate_new_price(last_price: float) -> float:
    """
    Price movement logic:
      - 15% chance  → big sale:  drop to 68–78 % of MRP
      - 85% chance  → normal:    ±5–10 % change on last price
    Price is clamped to [60% MRP, 98% MRP] to stay realistic.
    """
    roll = random.random()
    if roll < 0.15:                         # flash / festival sale
        new_price = MRP * random.uniform(0.68, 0.78)
    else:                                   # normal daily drift
        change = random.uniform(-0.10, 0.10)
        new_price = last_price * (1 + change)

    # Hard clamp
    new_price = max(MRP * 0.60, min(MRP * 0.98, new_price))
    return round(new_price, 2)


def insert_record(conn: sqlite3.Connection, price: float):
    discount = round((MRP - price) / MRP * 100, 2)
    conn.execute(
        """
        INSERT INTO price_history (product_name, price, mrp, discount_percent, date)
        VALUES (?, ?, ?, ?, ?)
        """,
        (PRODUCT_NAME, price, MRP, discount, datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
    )
    conn.commit()
    return discount


def run():
    init_db()
    with get_connection() as conn:
        last_price  = get_last_price(conn)
        new_price   = generate_new_price(last_price)
        discount    = insert_record(conn, new_price)

    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] "
          f"Updated price: ₹{new_price:,.2f}  |  Discount: {discount:.2f}%  |  MRP: ₹{MRP:,.2f}")


if __name__ == "__main__":
    run()
