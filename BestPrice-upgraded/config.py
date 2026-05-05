"""
config.py — Single source of truth for all BestPrice settings.
Override anything via environment variables or a .env file.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict

# ── Paths ────────────────────────────────────────────────────────────────────
ROOT_DIR = Path(__file__).parent
DB_PATH  = Path(os.getenv("BESTPRICE_DB_PATH", ROOT_DIR / "database.db"))

# ── Product catalogue ─────────────────────────────────────────────────────────
# Add more products here — the UI will show a selector automatically.
@dataclass
class Product:
    name: str
    mrp: float
    slug: str
    url: str = ""          # Flipkart / Amazon URL for real scraping
    currency: str = "₹"


PRODUCTS: Dict[str, Product] = {
    "samsung-m34": Product(
        slug="samsung-m34",
        name="Samsung Galaxy M34 5G",
        mrp=22_999.0,
        url="",  # add real URL for scraping
    ),
    "redmi-note13": Product(
        slug="redmi-note13",
        name="Redmi Note 13 5G",
        mrp=19_999.0,
        url="",
    ),
    "oneplus-nord-ce3": Product(
        slug="oneplus-nord-ce3",
        name="OnePlus Nord CE 3 Lite 5G",
        mrp=19_999.0,
        url="",
    ),
}

DEFAULT_PRODUCT_SLUG = os.getenv("BESTPRICE_PRODUCT", "samsung-m34")

# ── Model thresholds ──────────────────────────────────────────────────────────
BARGAIN_DISCOUNT_THRESHOLD = float(os.getenv("BARGAIN_THRESHOLD", "30"))
NEAR_HISTORICAL_LOW_PCT    = float(os.getenv("NEAR_LOW_PCT", "0.05"))
MIN_DISCOUNT_FOR_LOW_RULE  = float(os.getenv("MIN_DISCOUNT_LOW_RULE", "10"))

# ── Alerts ───────────────────────────────────────────────────────────────────
ALERT_EMAIL_FROM       = os.getenv("ALERT_EMAIL_FROM", "")
ALERT_EMAIL_TO         = os.getenv("ALERT_EMAIL_TO", "")
ALERT_SMTP_HOST        = os.getenv("ALERT_SMTP_HOST", "smtp.gmail.com")
ALERT_SMTP_PORT        = int(os.getenv("ALERT_SMTP_PORT", "587"))
ALERT_SMTP_PASSWORD    = os.getenv("ALERT_SMTP_PASSWORD", "")
ALERT_WEBHOOK_URL      = os.getenv("ALERT_WEBHOOK_URL", "")   # Discord / Slack

# ── Streamlit cache ───────────────────────────────────────────────────────────
CACHE_TTL_SECONDS = int(os.getenv("CACHE_TTL", "300"))

# ── Scraper ───────────────────────────────────────────────────────────────────
SCRAPER_REQUEST_TIMEOUT = int(os.getenv("SCRAPER_TIMEOUT", "15"))
SCRAPER_RETRY_ATTEMPTS  = int(os.getenv("SCRAPER_RETRIES", "3"))
