"""
update_price.py — Daily price updater.

Run manually:
    python update_price.py
    python update_price.py --slug samsung-m34    # specific product
    python update_price.py --all                 # all products

Cron (local):
    0 0 * * * cd /path/to/BestPrice && .venv/bin/python update_price.py --all >> logs/update.log 2>&1

GitHub Actions: see .github/workflows/update_price.yml
"""
from __future__ import annotations

import argparse
import logging
import sys
from datetime import datetime

from config import PRODUCTS, DEFAULT_PRODUCT_SLUG
from database import init_db, insert_price, get_last_price
from scraper import fetch_price
from model import predict_bargain
from alerts import notify_good_deal

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


def update_product(slug: str) -> dict:
    """Fetch, store, and evaluate price for one product. Returns a result dict."""
    if slug not in PRODUCTS:
        raise ValueError(f"Unknown product slug '{slug}'. Valid: {list(PRODUCTS)}")

    product    = PRODUCTS[slug]
    last_price = get_last_price(slug)

    price, source = fetch_price(product, last_price=last_price)
    discount      = insert_price(slug, product, price)

    hist_low  = last_price if last_price else price
    result    = predict_bargain(
        discount_percent=discount,
        historical_low=hist_low,
        current_price=price,
        mrp=product.mrp,
        product_slug=slug,
    )

    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    logger.info(
        "[%s] %s → %s%.2f (%.1f%% off) | source=%s | verdict=%s | conf=%s",
        ts, product.name, product.currency, price, discount,
        source, "DEAL" if result.is_good_deal else "skip", result.confidence_pct,
    )

    if result.is_good_deal:
        notify_good_deal(product, price, discount, result.confidence)

    return {
        "slug":        slug,
        "product":     product.name,
        "price":       price,
        "discount":    discount,
        "source":      source,
        "is_good_deal": result.is_good_deal,
        "confidence":  result.confidence,
    }


def run(slug: str = DEFAULT_PRODUCT_SLUG) -> None:
    """Single-product update — used by Streamlit's manual refresh button."""
    init_db()
    update_product(slug)


def run_all() -> None:
    """Update every product in the catalogue."""
    init_db()
    results = []
    for slug in PRODUCTS:
        try:
            results.append(update_product(slug))
        except Exception as exc:
            logger.error("Failed to update %s: %s", slug, exc)

    deals = [r for r in results if r["is_good_deal"]]
    logger.info(
        "Update complete: %d/%d products updated, %d deal(s) found.",
        len(results), len(PRODUCTS), len(deals),
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="BestPrice — daily price updater")
    group  = parser.add_mutually_exclusive_group()
    group.add_argument("--slug", default=DEFAULT_PRODUCT_SLUG,
                       help="Product slug to update (default: %(default)s)")
    group.add_argument("--all", action="store_true",
                       help="Update all products in the catalogue")
    args = parser.parse_args()

    if args.all:
        run_all()
    else:
        init_db()
        update_product(args.slug)
