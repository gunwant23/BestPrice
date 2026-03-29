"""
app.py — BestPrice Streamlit Dashboard
Run: streamlit run app.py
"""
import sqlite3
from datetime import datetime

import pandas as pd
import streamlit as st
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

from database import get_connection, init_db, MRP, PRODUCT_NAME
from model import predict_bargain

# ── Page config ─────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="BestPrice 🔍",
    page_icon="🏷️",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ── Custom CSS ───────────────────────────────────────────────────────────────
st.markdown(
    """
    <style>
    .main { background: #0f1117; }
    .metric-card {
        background: #1e2130;
        border-radius: 12px;
        padding: 20px 24px;
        text-align: center;
        border: 1px solid #2d3250;
    }
    .metric-card .label { color: #8892b0; font-size: 13px; letter-spacing: 1px; text-transform: uppercase; }
    .metric-card .value { color: #e6f1ff; font-size: 28px; font-weight: 700; margin-top: 6px; }
    .metric-card .sub   { color: #64ffda; font-size: 13px; margin-top: 4px; }
    .deal-badge {
        border-radius: 50px;
        padding: 10px 30px;
        font-size: 22px;
        font-weight: 800;
        display: inline-block;
        margin: 8px 0;
    }
    .good  { background: #0d3b2e; color: #64ffda; border: 2px solid #64ffda; }
    .bad   { background: #3b0d0d; color: #ff6b6b; border: 2px solid #ff6b6b; }
    </style>
    """,
    unsafe_allow_html=True,
)

# ── Data loading ─────────────────────────────────────────────────────────────
@st.cache_data(ttl=300)
def load_data() -> pd.DataFrame:
    init_db()
    with get_connection() as conn:
        df = pd.read_sql_query(
            "SELECT * FROM price_history ORDER BY date ASC", conn
        )
    df["date"] = pd.to_datetime(df["date"])
    return df


# ── Manual refresh ────────────────────────────────────────────────────────────
def trigger_update():
    from update_price import run
    run()
    st.cache_data.clear()


# ── Main ─────────────────────────────────────────────────────────────────────
def main():
    st.title("🏷️ BestPrice — Single Product Tracker")
    st.caption(f"Tracking **{PRODUCT_NAME}** · MRP ₹{MRP:,.0f}")

    df = load_data()

    if df.empty:
        st.warning("No data yet. Click **Simulate Today's Price** to get started.")
        if st.button("Simulate Today's Price"):
            trigger_update()
            st.rerun()
        return

    latest      = df.iloc[-1]
    current     = latest["price"]
    discount    = latest["discount_percent"]
    hist_low    = df["price"].min()
    hist_high   = df["price"].max()
    avg_price   = df["price"].mean()
    last_upd    = latest["date"].strftime("%d %b %Y, %I:%M %p")

    prediction  = predict_bargain(discount, hist_low, current, MRP)
    is_deal     = prediction["is_good_deal"]

    # ── Top row — metrics ────────────────────────────────────────────────────
    c1, c2, c3, c4 = st.columns(4)

    with c1:
        st.markdown(
            f"""<div class="metric-card">
                <div class="label">Current Price</div>
                <div class="value">₹{current:,.0f}</div>
                <div class="sub">Updated {last_upd}</div>
            </div>""",
            unsafe_allow_html=True,
        )

    with c2:
        st.markdown(
            f"""<div class="metric-card">
                <div class="label">Discount</div>
                <div class="value">{discount:.1f}%</div>
                <div class="sub">off MRP ₹{MRP:,.0f}</div>
            </div>""",
            unsafe_allow_html=True,
        )

    with c3:
        saving = MRP - current
        st.markdown(
            f"""<div class="metric-card">
                <div class="label">You Save</div>
                <div class="value">₹{saving:,.0f}</div>
                <div class="sub">vs MRP</div>
            </div>""",
            unsafe_allow_html=True,
        )

    with c4:
        st.markdown(
            f"""<div class="metric-card">
                <div class="label">All-Time Low</div>
                <div class="value">₹{hist_low:,.0f}</div>
                <div class="sub">over {len(df)} records</div>
            </div>""",
            unsafe_allow_html=True,
        )

    st.markdown("<br>", unsafe_allow_html=True)

    # ── Deal verdict ─────────────────────────────────────────────────────────
    badge_cls   = "good" if is_deal else "bad"
    badge_text  = "✅ GREAT DEAL — BUY NOW!" if is_deal else "❌ Not Worth It Yet"
    method_tag  = prediction["method"]
    reason_text = prediction["reason"]
    confidence  = prediction["confidence"]

    col_a, col_b = st.columns([1, 2])
    with col_a:
        st.markdown(
            f'<div class="deal-badge {badge_cls}">{badge_text}</div>',
            unsafe_allow_html=True,
        )
        st.caption(f"**Method:** {method_tag} · **Confidence:** {confidence*100:.0f}%")
        st.caption(f"**Why:** {reason_text}")

    with col_b:
        # Mini gauge via progress bar
        st.markdown("**Deal Score**")
        score = int(min(discount / 50 * 100, 100))
        st.progress(score)
        st.caption(f"Score: {score}/100  (≥ 60 = good deal)")

    st.divider()

    # ── Charts ───────────────────────────────────────────────────────────────
    tab1, tab2, tab3 = st.tabs(["📈 Price History", "📊 Discount Distribution", "🔍 Stats"])

    with tab1:
        fig, ax = plt.subplots(figsize=(12, 4))
        fig.patch.set_facecolor("#0f1117")
        ax.set_facecolor("#1e2130")

        ax.plot(df["date"], df["price"], color="#64ffda", linewidth=1.8, label="Price")
        ax.axhline(hist_low,  color="#ff6b6b", linewidth=1, linestyle="--", label=f"All-time Low ₹{hist_low:,.0f}")
        ax.axhline(avg_price, color="#f8c555", linewidth=1, linestyle=":",  label=f"Avg ₹{avg_price:,.0f}")
        ax.axhline(MRP,       color="#8892b0", linewidth=0.8, linestyle="-.", alpha=0.6, label=f"MRP ₹{MRP:,.0f}")

        ax.xaxis.set_major_formatter(mdates.DateFormatter("%d %b"))
        ax.xaxis.set_major_locator(mdates.WeekdayLocator(interval=1))
        plt.xticks(rotation=30, color="#8892b0", fontsize=9)
        plt.yticks(color="#8892b0", fontsize=9)
        ax.set_ylabel("Price (₹)", color="#8892b0")
        ax.tick_params(colors="#8892b0")
        for spine in ax.spines.values():
            spine.set_edgecolor("#2d3250")
        ax.legend(facecolor="#1e2130", labelcolor="#e6f1ff", fontsize=9, framealpha=0.8)
        ax.set_title(f"{PRODUCT_NAME} — Price Over Time", color="#e6f1ff", fontsize=12)

        st.pyplot(fig)
        plt.close(fig)

    with tab2:
        fig2, ax2 = plt.subplots(figsize=(10, 4))
        fig2.patch.set_facecolor("#0f1117")
        ax2.set_facecolor("#1e2130")

        ax2.hist(
            df["discount_percent"], bins=20,
            color="#64ffda", edgecolor="#0f1117", alpha=0.85,
        )
        ax2.axvline(30, color="#ff6b6b", linewidth=1.5, linestyle="--", label="30% Bargain threshold")
        ax2.set_xlabel("Discount (%)", color="#8892b0")
        ax2.set_ylabel("Frequency", color="#8892b0")
        ax2.set_title("Discount Distribution", color="#e6f1ff", fontsize=12)
        plt.xticks(color="#8892b0"); plt.yticks(color="#8892b0")
        for spine in ax2.spines.values():
            spine.set_edgecolor("#2d3250")
        ax2.legend(facecolor="#1e2130", labelcolor="#e6f1ff", fontsize=9)

        st.pyplot(fig2)
        plt.close(fig2)

    with tab3:
        col1, col2 = st.columns(2)
        with col1:
            st.markdown("#### Price Statistics")
            stats_df = pd.DataFrame({
                "Metric": ["Current Price", "MRP", "All-Time Low", "All-Time High", "Average Price", "Std Dev"],
                "Value": [
                    f"₹{current:,.2f}",
                    f"₹{MRP:,.2f}",
                    f"₹{hist_low:,.2f}",
                    f"₹{hist_high:,.2f}",
                    f"₹{avg_price:,.2f}",
                    f"₹{df['price'].std():,.2f}",
                ],
            })
            st.dataframe(stats_df, hide_index=True, use_container_width=True)

        with col2:
            st.markdown("#### Bargain Frequency")
            good_deals = (df["discount_percent"] >= 30).sum()
            pct        = good_deals / len(df) * 100
            st.metric("Days with ≥ 30% discount", f"{good_deals} / {len(df)}")
            st.metric("Bargain frequency", f"{pct:.1f}%")
            st.metric("Best discount ever", f"{df['discount_percent'].max():.1f}%")
            st.metric("Best price ever", f"₹{hist_low:,.0f}")

        st.markdown("#### Recent Price History")
        recent = df.sort_values("date", ascending=False).head(10).copy()
        recent["date"] = recent["date"].dt.strftime("%d %b %Y %H:%M")
        recent["price"] = recent["price"].map("₹{:,.2f}".format)
        recent["discount_percent"] = recent["discount_percent"].map("{:.1f}%".format)
        st.dataframe(
            recent[["date", "price", "discount_percent"]].rename(
                columns={"date": "Date", "price": "Price", "discount_percent": "Discount"}
            ),
            hide_index=True,
            use_container_width=True,
        )

    st.divider()

    # ── Simulate / Refresh ────────────────────────────────────────────────────
    col_btn1, col_btn2, _ = st.columns([1, 1, 4])
    with col_btn1:
        if st.button("🔄 Simulate Today's Price", use_container_width=True):
            trigger_update()
            st.rerun()
    with col_btn2:
        if st.button("🗑️ Reset All Data", use_container_width=True):
            import os
            db = os.path.join(os.path.dirname(__file__), "database.db")
            if os.path.exists(db):
                os.remove(db)
            st.cache_data.clear()
            st.rerun()

    st.caption(f"Last data point: {last_upd} · {len(df)} total records · Model: {method_tag}")


if __name__ == "__main__":
    main()
