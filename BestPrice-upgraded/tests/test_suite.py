"""
tests/test_suite.py — BestPrice full test suite.

Run:
    pytest tests/ -v
    pytest tests/ -v --cov=. --cov-report=term-missing
"""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

# ── Make sure the repo root is on PYTHONPATH ─────────────────────────────────
sys.path.insert(0, str(Path(__file__).parent.parent))


# ═══════════════════════════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.fixture(autouse=True)
def isolated_db(tmp_path, monkeypatch):
    """Each test gets its own temporary SQLite database."""
    db = tmp_path / "test.db"
    monkeypatch.setenv("BESTPRICE_DB_PATH", str(db))

    # Re-import config with the patched env var
    import importlib
    import config as cfg
    monkeypatch.setattr(cfg, "DB_PATH", db)

    import database as db_module
    monkeypatch.setattr(db_module, "DB_PATH", db)

    import model as model_module
    monkeypatch.setattr(model_module, "DB_PATH", db)

    yield db


# ═══════════════════════════════════════════════════════════════════════════════
# config.py
# ═══════════════════════════════════════════════════════════════════════════════

class TestConfig:
    def test_products_not_empty(self):
        from config import PRODUCTS
        assert len(PRODUCTS) >= 1

    def test_product_has_required_fields(self):
        from config import PRODUCTS
        for slug, prod in PRODUCTS.items():
            assert prod.name
            assert prod.mrp > 0
            assert prod.slug == slug

    def test_default_slug_is_valid(self):
        from config import PRODUCTS, DEFAULT_PRODUCT_SLUG
        assert DEFAULT_PRODUCT_SLUG in PRODUCTS

    def test_bargain_threshold_reasonable(self):
        from config import BARGAIN_DISCOUNT_THRESHOLD
        assert 5 <= BARGAIN_DISCOUNT_THRESHOLD <= 60


# ═══════════════════════════════════════════════════════════════════════════════
# database.py
# ═══════════════════════════════════════════════════════════════════════════════

class TestDatabase:
    def test_init_creates_table(self, isolated_db):
        from database import init_db, get_connection
        init_db()
        with get_connection() as conn:
            tables = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        assert any("price_history" in t[0] for t in tables)

    def test_seed_inserts_rows(self, isolated_db):
        from database import init_db, get_connection
        init_db()
        with get_connection() as conn:
            count = conn.execute("SELECT COUNT(*) FROM price_history").fetchone()[0]
        # 60 days × number of products
        from config import PRODUCTS
        assert count == 60 * len(PRODUCTS)

    def test_insert_price(self, isolated_db):
        from database import init_db, insert_price, get_connection
        from config import PRODUCTS
        init_db()
        slug, product = next(iter(PRODUCTS.items()))
        discount = insert_price(slug, product, product.mrp * 0.75)
        assert abs(discount - 25.0) < 0.1
        with get_connection() as conn:
            last = conn.execute(
                "SELECT price FROM price_history WHERE product_slug=? ORDER BY date DESC LIMIT 1",
                (slug,)
            ).fetchone()
        assert last["price"] == product.mrp * 0.75

    def test_get_last_price_returns_latest(self, isolated_db):
        from database import init_db, insert_price, get_last_price
        from config import PRODUCTS
        init_db()
        slug, product = next(iter(PRODUCTS.items()))
        target = product.mrp * 0.70
        insert_price(slug, product, target)
        result = get_last_price(slug)
        assert result == target

    def test_get_last_price_none_for_unknown_slug(self, isolated_db):
        from database import init_db, get_last_price
        init_db()
        assert get_last_price("nonexistent-slug-xyz") is None

    def test_double_init_is_idempotent(self, isolated_db):
        from database import init_db, get_connection
        init_db()
        init_db()
        with get_connection() as conn:
            count = conn.execute("SELECT COUNT(*) FROM price_history").fetchone()[0]
        from config import PRODUCTS
        assert count == 60 * len(PRODUCTS)   # no double-seeding

    def test_price_constraint(self, isolated_db):
        """Price must be > 0 — DB should reject negatives."""
        import sqlite3
        from database import init_db, get_connection
        init_db()
        with pytest.raises((sqlite3.IntegrityError, sqlite3.OperationalError)):
            with get_connection() as conn:
                conn.execute(
                    "INSERT INTO price_history (product_slug,product_name,price,mrp,discount_percent) "
                    "VALUES ('x','x',-1,10000,110)"
                )
                conn.commit()


# ═══════════════════════════════════════════════════════════════════════════════
# model.py
# ═══════════════════════════════════════════════════════════════════════════════

class TestModel:
    MRP = 22_999.0

    @pytest.mark.parametrize("discount,hist_low,price,expected", [
        (40.0, 13_000.0, 13_800.0, True),   # big discount
        (5.0,  20_000.0, 21_850.0, False),  # tiny discount
        (29.9, 16_000.0, 16_100.0, True),   # near historical low
        (0.0,  22_000.0, 22_999.0, False),  # full MRP
        (60.0,  9_200.0,  9_200.0, True),   # crazy deal
        (12.0, 18_000.0, 20_239.0, False),  # moderate discount, not near low
    ])
    def test_rule_based(self, discount, hist_low, price, expected):
        from model import predict_bargain
        result = predict_bargain(discount, hist_low, price, self.MRP, use_ml=False)
        assert result.is_good_deal == expected

    def test_result_has_all_fields(self):
        from model import predict_bargain
        r = predict_bargain(35.0, 14_000.0, 14_950.0, self.MRP, use_ml=False)
        assert isinstance(r.is_good_deal, bool)
        assert 0.0 <= r.confidence <= 1.0
        assert r.method
        assert r.reason

    def test_confidence_bounded(self):
        from model import predict_bargain
        for disc in [0, 15, 30, 50, 99]:
            r = predict_bargain(float(disc), 10_000.0, self.MRP * 0.6, self.MRP, use_ml=False)
            assert 0.0 <= r.confidence <= 1.0

    def test_deal_score_bounded(self):
        from model import predict_bargain
        r = predict_bargain(40.0, 13_000.0, 13_800.0, self.MRP, use_ml=False)
        assert 0 <= r.deal_score <= 100

    def test_verdict_strings(self):
        from model import predict_bargain
        good = predict_bargain(40.0, 13_000.0, 13_800.0, self.MRP, use_ml=False)
        bad  = predict_bargain(5.0,  20_000.0, 21_850.0, self.MRP, use_ml=False)
        assert "BUY" in good.verdict
        assert "Not Worth" in bad.verdict

    def test_no_hist_low(self):
        from model import predict_bargain
        r = predict_bargain(35.0, None, 14_950.0, self.MRP, use_ml=False)
        assert isinstance(r.is_good_deal, bool)

    def test_ml_falls_back_gracefully(self, isolated_db):
        """ML should fall back to rule-based when there's not enough data."""
        from model import predict_bargain
        # DB exists but is empty → ML returns None → rule-based kicks in
        r = predict_bargain(35.0, 14_000.0, 14_950.0, self.MRP,
                            product_slug="samsung-m34", use_ml=True)
        assert isinstance(r.is_good_deal, bool)


# ═══════════════════════════════════════════════════════════════════════════════
# scraper.py
# ═══════════════════════════════════════════════════════════════════════════════

class TestScraper:
    def test_simulate_price_in_range(self):
        from scraper import simulate_price
        mrp = 22_999.0
        for _ in range(200):
            p = simulate_price(mrp * 0.88, mrp)
            assert mrp * 0.55 <= p <= mrp * 0.98

    def test_simulate_price_deterministic_ish(self):
        """Same inputs should produce varied but bounded output."""
        from scraper import simulate_price
        prices = {simulate_price(19_000.0, 22_999.0) for _ in range(30)}
        assert len(prices) > 1    # it's random, not constant

    def test_fetch_price_no_url_returns_simulated(self):
        from scraper import fetch_price
        from config import Product
        prod = Product(slug="test", name="Test", mrp=20_000.0, url="")
        price, source = fetch_price(prod, last_price=18_000.0)
        assert source == "simulated"
        assert 20_000 * 0.55 <= price <= 20_000 * 0.98

    def test_fetch_price_bad_url_falls_back(self):
        from scraper import fetch_price
        from config import Product
        prod = Product(slug="test", name="Test", mrp=20_000.0,
                       url="https://www.flipkart.com/fake-product-url")
        # This will fail HTTP → fall back to simulation
        price, source = fetch_price(prod, last_price=18_000.0)
        assert source == "simulated"


# ═══════════════════════════════════════════════════════════════════════════════
# update_price.py
# ═══════════════════════════════════════════════════════════════════════════════

class TestUpdatePrice:
    def test_update_product_inserts_row(self, isolated_db):
        from database import init_db, get_connection
        from update_price import update_product
        from config import PRODUCTS

        init_db()
        slug = next(iter(PRODUCTS))
        count_before = 0
        with get_connection() as conn:
            count_before = conn.execute(
                "SELECT COUNT(*) FROM price_history WHERE product_slug=?", (slug,)
            ).fetchone()[0]

        update_product(slug)

        with get_connection() as conn:
            count_after = conn.execute(
                "SELECT COUNT(*) FROM price_history WHERE product_slug=?", (slug,)
            ).fetchone()[0]

        assert count_after == count_before + 1

    def test_update_product_returns_dict(self, isolated_db):
        from database import init_db
        from update_price import update_product
        from config import PRODUCTS

        init_db()
        slug = next(iter(PRODUCTS))
        result = update_product(slug)
        assert "price" in result
        assert "discount" in result
        assert "is_good_deal" in result

    def test_update_product_invalid_slug(self, isolated_db):
        from database import init_db
        from update_price import update_product

        init_db()
        with pytest.raises(ValueError, match="Unknown product slug"):
            update_product("this-does-not-exist")

    def test_run_all(self, isolated_db):
        from database import init_db, get_connection
        from update_price import run_all
        from config import PRODUCTS

        init_db()
        run_all()

        with get_connection() as conn:
            for slug in PRODUCTS:
                count = conn.execute(
                    "SELECT COUNT(*) FROM price_history WHERE product_slug=?", (slug,)
                ).fetchone()[0]
                assert count > 60   # seeded 60 + at least 1 new
