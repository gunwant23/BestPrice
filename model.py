"""
model.py
--------
Two-tier bargain detection:

1. Rule-based  (always works, zero deps beyond stdlib)
2. ML fallback (Logistic Regression trained on historical data)
   — used only when sklearn is available AND we have >= 10 rows.

Public API
----------
    from model import predict_bargain
    result = predict_bargain(discount_percent, historical_low_price, current_price, mrp)
    # Returns dict: {"is_good_deal": bool, "confidence": float, "method": str, "reason": str}
"""
from __future__ import annotations
from typing import Optional


# ---------------------------------------------------------------------------
# Thresholds
# ---------------------------------------------------------------------------
BARGAIN_DISCOUNT_THRESHOLD = 30.0   # >= 30% off MRP -> good deal
NEAR_HISTORICAL_LOW_PCT    = 0.05   # within 5% of historical low
MIN_DISCOUNT_FOR_LOW_RULE  = 10.0   # must also have >= 10% off MRP for the low-rule to fire


# ---------------------------------------------------------------------------
# Rule-based classifier (primary)
# ---------------------------------------------------------------------------
def _rule_based(
    discount_percent: float,
    historical_low: Optional[float],
    current_price: float,
) -> dict:
    reasons = []

    # Condition A: big discount
    if discount_percent >= BARGAIN_DISCOUNT_THRESHOLD:
        reasons.append(f"discount {discount_percent:.1f}% >= {BARGAIN_DISCOUNT_THRESHOLD}%")

    # Condition B: near historical low AND meaningful discount
    if historical_low is not None and discount_percent >= MIN_DISCOUNT_FOR_LOW_RULE:
        gap = (current_price - historical_low) / max(historical_low, 1)
        if gap <= NEAR_HISTORICAL_LOW_PCT:
            reasons.append(f"price within {NEAR_HISTORICAL_LOW_PCT*100:.0f}% of all-time low")

    is_good = len(reasons) > 0
    confidence = min(1.0, discount_percent / 100 + (0.2 if is_good else 0))
    return {
        "is_good_deal": is_good,
        "confidence": round(confidence, 3),
        "method": "rule-based",
        "reason": "; ".join(reasons) if reasons else "discount too small / not near historical low",
    }


# ---------------------------------------------------------------------------
# ML classifier (optional enhancement)
# ---------------------------------------------------------------------------
def _ml_predict(discount_percent: float, mrp: float, current_price: float) -> dict | None:
    """Train a tiny Logistic Regression on historical data and predict."""
    try:
        import sqlite3, os
        from sklearn.linear_model import LogisticRegression
        import numpy as np

        db_path = os.path.join(os.path.dirname(__file__), "database.db")
        if not os.path.exists(db_path):
            return None

        conn = sqlite3.connect(db_path)
        rows = conn.execute(
            "SELECT price, discount_percent FROM price_history ORDER BY date"
        ).fetchall()
        conn.close()

        if len(rows) < 10:
            return None

        prices    = np.array([r[0] for r in rows])
        discounts = np.array([r[1] for r in rows])

        # Label: 1 if discount >= threshold OR price in bottom-20th percentile
        low_20  = np.percentile(prices, 20)
        labels  = ((discounts >= BARGAIN_DISCOUNT_THRESHOLD) | (prices <= low_20)).astype(int)

        if labels.sum() == 0 or labels.sum() == len(labels):
            return None   # degenerate dataset — fall back to rules

        X   = np.column_stack([discounts, prices / mrp])
        clf = LogisticRegression(max_iter=500)
        clf.fit(X, labels)

        x_new = np.array([[discount_percent, current_price / mrp]])
        pred  = clf.predict(x_new)[0]
        prob  = clf.predict_proba(x_new)[0][1]

        return {
            "is_good_deal": bool(pred),
            "confidence"  : round(float(prob), 3),
            "method"      : "logistic-regression",
            "reason"      : f"ML confidence {prob*100:.1f}% (trained on {len(rows)} records)",
        }
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------
def predict_bargain(
    discount_percent: float,
    historical_low  : Optional[float],
    current_price   : float,
    mrp             : float,
    use_ml          : bool = True,
) -> dict:
    """
    Returns a dict with keys:
        is_good_deal : bool
        confidence   : float  (0-1)
        method       : str
        reason       : str
    """
    if use_ml:
        ml_result = _ml_predict(discount_percent, mrp, current_price)
        if ml_result is not None:
            return ml_result

    return _rule_based(discount_percent, historical_low, current_price)


# ---------------------------------------------------------------------------
# Self-test
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    cases = [
        # (discount, hist_low, price, mrp, expected, label)
        (40.0, 13000.0, 13800.0, 22999.0, True,  "Flash sale"),
        (5.0,  20000.0, 21850.0, 22999.0, False, "Tiny discount"),
        (29.9, 16000.0, 16100.0, 22999.0, True,  "Near hist-low"),
        (0.0,  22000.0, 22999.0, 22999.0, False, "Full MRP price"),
        (60.0, 9200.0,  9200.0,  22999.0, True,  "Crazy deal"),
        (35.0, 14000.0, 14950.0, 22999.0, True,  "Good discount"),
        (12.0, 18000.0, 20239.0, 22999.0, False, "Moderate discount"),
    ]
    all_ok = True
    for disc, hl, price, mrp, expected, label in cases:
        r  = predict_bargain(disc, hl, price, mrp, use_ml=False)
        ok = r["is_good_deal"] == expected
        all_ok = all_ok and ok
        tag = "GOOD DEAL" if r["is_good_deal"] else "Skip"
        print(f"{'OK' if ok else 'FAIL'}  {label:22s} -> {tag:9s}  conf={r['confidence']}  reason={r['reason']}")

    print()
    print("All tests PASSED" if all_ok else "SOME TESTS FAILED — check above")
