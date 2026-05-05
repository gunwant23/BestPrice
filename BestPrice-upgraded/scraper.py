"""
scraper.py — Price fetching for BestPrice.

Strategy
--------
1. If the product has a real URL configured → try HTTP scraping.
2. If scraping fails (bot protection, network error, etc.) → fall back to
   realistic price simulation so the app keeps working in demo / dev mode.

Adding a new source
-------------------
Implement a function with signature:

    def scrape_<source>(url: str) -> float | None

and register it in SCRAPERS below.
"""
from __future__ import annotations

import logging
import random
import time
from typing import Callable, Optional

from config import (
    Product,
    SCRAPER_REQUEST_TIMEOUT,
    SCRAPER_RETRY_ATTEMPTS,
)

logger = logging.getLogger(__name__)


# ── Source scrapers ───────────────────────────────────────────────────────────

def _scrape_flipkart(url: str) -> Optional[float]:
    """
    Attempt to scrape the current price from a Flipkart product page.

    NOTE: Flipkart uses heavy JS rendering and aggressive anti-bot measures.
    This implementation uses static HTML parsing — it will work on cached /
    server-side rendered pages but may be blocked on full loads.
    For production, consider using a paid proxy service or Flipkart's affiliate API.
    """
    try:
        import requests
        from bs4 import BeautifulSoup

        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            "Accept-Language": "en-IN,en;q=0.9",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        }

        resp = requests.get(url, headers=headers, timeout=SCRAPER_REQUEST_TIMEOUT)
        resp.raise_for_status()

        soup = BeautifulSoup(resp.text, "html.parser")

        # Flipkart price is in <div class="_30jeq3 _16Jk6d"> or similar dynamic classes.
        # We check multiple known selectors defensively.
        selectors = [
            "div._30jeq3._16Jk6d",
            "div._30jeq3",
            "div.Nx9bqj",
        ]
        for sel in selectors:
            tag = soup.select_one(sel)
            if tag:
                raw = tag.get_text(strip=True).replace("₹", "").replace(",", "").strip()
                return float(raw)

        logger.warning("[scraper] Flipkart: price element not found at %s", url)
        return None

    except Exception as exc:
        logger.warning("[scraper] Flipkart scrape failed: %s", exc)
        return None


def _scrape_amazon(url: str) -> Optional[float]:
    """Scrape Amazon India product price."""
    try:
        import requests
        from bs4 import BeautifulSoup

        headers = {
            "User-Agent": (
                "Mozilla/5.0 (X11; Linux x86_64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            "Accept-Language": "en-IN",
        }

        resp = requests.get(url, headers=headers, timeout=SCRAPER_REQUEST_TIMEOUT)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")

        # Amazon price selectors
        for sel in ["span.a-price-whole", "#priceblock_ourprice", "#priceblock_dealprice"]:
            tag = soup.select_one(sel)
            if tag:
                raw = tag.get_text(strip=True).replace(",", "").replace(".", "").replace("₹", "").strip()
                if raw.isdigit():
                    return float(raw)

        logger.warning("[scraper] Amazon: price element not found at %s", url)
        return None

    except Exception as exc:
        logger.warning("[scraper] Amazon scrape failed: %s", exc)
        return None


# Map URL domain fragment → scrape function
SCRAPERS: dict[str, Callable[[str], Optional[float]]] = {
    "flipkart.com": _scrape_flipkart,
    "amazon.in":    _scrape_amazon,
}


def _detect_scraper(url: str) -> Optional[Callable[[str], Optional[float]]]:
    for domain, fn in SCRAPERS.items():
        if domain in url:
            return fn
    return None


# ── Simulation fallback ───────────────────────────────────────────────────────

def simulate_price(last_price: float, mrp: float) -> float:
    """
    Realistic Markov-style price simulation.

      • 15 % chance → flash sale: 68–78 % of MRP
      • 85 % chance → daily drift: ±10 % of last price
      • Hard clamp: [55 % MRP, 98 % MRP]
    """
    roll = random.random()
    if roll < 0.15:
        new_price = mrp * random.uniform(0.68, 0.78)
    else:
        change = random.uniform(-0.10, 0.10)
        new_price = last_price * (1 + change)

    new_price = max(mrp * 0.55, min(mrp * 0.98, new_price))
    return round(new_price, 2)


# ── Public API ────────────────────────────────────────────────────────────────

def fetch_price(
    product: Product,
    last_price: Optional[float] = None,
) -> tuple[float, str]:
    """
    Return (price, source) where source is 'scraped' or 'simulated'.

    Tries real scraping if a URL is configured; falls back to simulation.
    Retries up to SCRAPER_RETRY_ATTEMPTS times with back-off.
    """
    if product.url:
        scraper_fn = _detect_scraper(product.url)
        if scraper_fn:
            for attempt in range(1, SCRAPER_RETRY_ATTEMPTS + 1):
                price = scraper_fn(product.url)
                if price is not None and price > 0:
                    logger.info(
                        "[scraper] ✅ %s → %s%.2f (attempt %d)",
                        product.name, product.currency, price, attempt,
                    )
                    return price, "scraped"
                if attempt < SCRAPER_RETRY_ATTEMPTS:
                    time.sleep(2 ** attempt)   # exponential back-off

            logger.warning("[scraper] All attempts failed; switching to simulation.")

    # Simulation fallback
    fallback_last = last_price if last_price else product.mrp * 0.88
    price = simulate_price(fallback_last, product.mrp)
    return price, "simulated"


if __name__ == "__main__":
    from config import PRODUCTS
    for slug, prod in PRODUCTS.items():
        price, source = fetch_price(prod)
        discount = (prod.mrp - price) / prod.mrp * 100
        print(f"{prod.name}: {prod.currency}{price:,.2f}  ({discount:.1f}% off)  [{source}]")
