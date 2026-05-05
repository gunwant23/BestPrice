"""
model.py — Two-tier bargain classifier.

Tier 1 (always active)  : Rule-based heuristics — instant, zero dependencies.
Tier 2 (when available) : Logistic Regression trained on historical data.

Public API
----------
    from model import predict_bargain, BargainResult

    result = predict_bargain(
        discount_percent=35.0,
        historical_low=14_000.0,
        current_price=14_950.0,
        mrp=22_999.0,
    )
    print(result.is_good_deal, result.confidence, result.reason)
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from config import (
    BARGAIN_DISCOUNT_THRESHOLD,
    MIN_DISCOUNT_FOR_LOW_RULE,
    NEAR_HISTORICAL_LOW_PCT,
    DB_PATH,
)


# ── Result dataclass ──────────────────────────────────────────────────────────
@dataclass
class BargainResult:
    is_good_deal: bool
    confidence: float          # 0.0 – 1.0
    method: str
    reason: str

    # Convenience
    @property
    def verdict(self) -> str:
        return "✅ GREAT DEAL — BUY NOW!" if self.is_good_deal else "❌ Not Worth It Yet"

    @property
    def confidence_pct(self) -> str:
        return f"{self.confidence * 100:.0f}%"

    @property
    def deal_score(self) -> int:
        """0-100 score suitable for a progress bar."""
        return int(min(100, self.confidence * 100))


# ── Rule-based (Tier 1) ───────────────────────────────────────────────────────
def _rule_based(
    discount_percent: float,
    historical_low: Optional[float],
    current_price: float,
) -> BargainResult:
    reasons: list[str] = []

    if discount_percent >= BARGAIN_DISCOUNT_THRESHOLD:
        reasons.append(f"discount {discount_percent:.1f}% ≥ {BARGAIN_DISCOUNT_THRESHOLD:.0f}% threshold")

    if (
        historical_low is not None
        and discount_percent >= MIN_DISCOUNT_FOR_LOW_RULE
    ):
        gap = (current_price - historical_low) / max(historical_low, 1)
        if gap <= NEAR_HISTORICAL_LOW_PCT:
            reasons.append(
                f"price within {NEAR_HISTORICAL_LOW_PCT * 100:.0f}% of all-time low"
            )

    is_good = bool(reasons)
    # Calibrated confidence: bonus for being near hist-low AND having big discount
    raw_conf = min(1.0, discount_percent / 70 + (0.15 if is_good else 0))
    confidence = round(max(0.05, min(0.99, raw_conf)), 3)

    return BargainResult(
        is_good_deal=is_good,
        confidence=confidence,
        method="rule-based",
        reason="; ".join(reasons) if reasons else "discount too small / not near historical low",
    )


# ── ML (Tier 2) ───────────────────────────────────────────────────────────────
def _ml_predict(
    discount_percent: float,
    mrp: float,
    current_price: float,
    product_slug: str,
) -> Optional[BargainResult]:
    """Train Logistic Regression on-the-fly; returns None on any failure."""
    try:
        import sqlite3

        import numpy as np
        from sklearn.linear_model import LogisticRegression
        from sklearn.preprocessing import StandardScaler

        if not DB_PATH.exists():
            return None

        conn = sqlite3.connect(str(DB_PATH))
        rows = conn.execute(
            "SELECT price, discount_percent FROM price_history WHERE product_slug=? ORDER BY date",
            (product_slug,),
        ).fetchall()
        conn.close()

        if len(rows) < 20:          # need enough data for a meaningful model
            return None

        prices    = np.array([r[0] for r in rows], dtype=float)
        discounts = np.array([r[1] for r in rows], dtype=float)
        low_20    = np.percentile(prices, 20)
        labels    = (
            (discounts >= BARGAIN_DISCOUNT_THRESHOLD) | (prices <= low_20)
        ).astype(int)

        if labels.sum() == 0 or labels.sum() == len(labels):
            return None   # degenerate — all same class

        X = np.column_stack([discounts, prices / mrp, prices / prices.max()])
        scaler = StandardScaler()
        X_scaled = scaler.fit_transform(X)

        clf = LogisticRegression(max_iter=1000, C=1.0, class_weight="balanced")
        clf.fit(X_scaled, labels)

        x_new   = scaler.transform([[discount_percent, current_price / mrp, current_price / prices.max()]])
        pred    = clf.predict(x_new)[0]
        prob    = clf.predict_proba(x_new)[0][1]

        return BargainResult(
            is_good_deal=bool(pred),
            confidence=round(float(prob), 3),
            method="logistic-regression",
            reason=(
                f"ML confidence {prob * 100:.1f}% "
                f"(trained on {len(rows)} records for this product)"
            ),
        )

    except Exception:
        return None


# ── Public API ────────────────────────────────────────────────────────────────
def predict_bargain(
    discount_percent: float,
    historical_low: Optional[float],
    current_price: float,
    mrp: float,
    product_slug: str = "default",
    use_ml: bool = True,
) -> BargainResult:
    """
    Classify whether the current price is a good deal.

    Parameters
    ----------
    discount_percent : float   — (MRP - price) / MRP * 100
    historical_low   : float   — lowest recorded price (can be None)
    current_price    : float   — today's price
    mrp              : float   — manufacturer's recommended price
    product_slug     : str     — used to filter DB records for ML
    use_ml           : bool    — set False to force rule-based only

    Returns
    -------
    BargainResult dataclass
    """
    if use_ml:
        ml = _ml_predict(discount_percent, mrp, current_price, product_slug)
        if ml is not None:
            return ml

    return _rule_based(discount_percent, historical_low, current_price)


# ── Self-test ─────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    CASES = [
        (40.0, 13_000.0, 13_800.0, 22_999.0, True,  "Flash sale"),
        (5.0,  20_000.0, 21_850.0, 22_999.0, False, "Tiny discount"),
        (29.9, 16_000.0, 16_100.0, 22_999.0, True,  "Near hist-low"),
        (0.0,  22_000.0, 22_999.0, 22_999.0, False, "Full MRP price"),
        (60.0,  9_200.0,  9_200.0, 22_999.0, True,  "Crazy deal"),
        (35.0, 14_000.0, 14_950.0, 22_999.0, True,  "Good discount"),
        (12.0, 18_000.0, 20_239.0, 22_999.0, False, "Moderate discount"),
    ]

    all_ok = True
    for disc, hl, price, mrp, expected, label in CASES:
        r  = predict_bargain(disc, hl, price, mrp, use_ml=False)
        ok = r.is_good_deal == expected
        all_ok = all_ok and ok
        status = "OK  " if ok else "FAIL"
        print(f"{status}  {label:22s}  {r.verdict:30s}  conf={r.confidence_pct}  {r.reason}")

    print()
    print("✅ All tests PASSED" if all_ok else "❌ SOME TESTS FAILED — check above")
