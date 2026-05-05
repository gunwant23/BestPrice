"""
app.py — BestPrice Streamlit Dashboard
Run: streamlit run app.py
"""
from __future__ import annotations

import os
from datetime import datetime

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import pandas as pd
import streamlit as st

from config import CACHE_TTL_SECONDS, PRODUCTS, DEFAULT_PRODUCT_SLUG
from database import get_connection, init_db
from model import predict_bargain

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="BestPrice 🔍",
    page_icon="🏷️",
    layout="wide",
    initial_sidebar_state="expanded",
    menu_items={
        "Get help": "https://github.com/gunwant23/BestPrice",
        "Report a bug": "https://github.com/gunwant23/BestPrice/issues",
        "About": "# BestPrice\nAI-powered price tracker for Indian e-commerce.",
    },
)

# ── Theme / CSS ───────────────────────────────────────────────────────────────
st.markdown(
    """
    <style>
    /* Dark background */
    .main, [data-testid="stAppViewContainer"] { background: #0f1117; }
    [data-testid="stSidebar"] { background: #161b2e; border-right: 1px solid #2d3250; }

    /* Metric cards */
    .metric-card {
        background: #1e2130;
        border-radius: 14px;
        padding: 20px 24px;
        text-align: center;
        border: 1px solid #2d3250;
        transition: border-color .2s;
    }
    .metric-card:hover { border-color: #64ffda; }
    .metric-card .label {
        color: #8892b0; font-size: 11px;
        letter-spacing: 1.5px; text-transform: uppercase;
    }
    .metric-card .value {
        color: #e6f1ff; font-size: 30px;
        font-weight: 800; margin-top: 8px;
    }
    .metric-card .sub { color: #64ffda; font-size: 12px; margin-top: 4px; }

    /* Deal badge */
    .deal-badge {
        border-radius: 50px; padding: 10px 32px;
        font-size: 20px; font-weight: 800;
        display: inline-block; margin: 8px 0;
    }
    .good { background:#0d3b2e; color:#64ffda; border:2px solid #64ffda; }
    .bad  { background:#3b0d0d; color:#ff6b6b; border:2px solid #ff6b6b; }

    /* Sidebar section headers */
    .sidebar-header {
        color: #64ffda; font-size: 11px; font-weight: 700;
        letter-spacing: 1.5px; text-transform: uppercase;
        margin: 16px 0 8px;
    }

    /* Remove top padding on main */
    .block-container { padding-top: 1.5rem; }

    /* Dataframe tweaks */
    [data-testid="stDataFrame"] { border-radius: 10px; overflow: hidden; }
    </style>
    """,
    unsafe_allow_html=True,
)

# ── Matplotlib dark theme ─────────────────────────────────────────────────────
plt.rcParams.update({
    "figure.facecolor":  "#0f1117",
    "axes.facecolor":    "#1e2130",
    "axes.edgecolor":    "#2d3250",
    "axes.labelcolor":   "#8892b0",
    "xtick.color":       "#8892b0",
    "ytick.color":       "#8892b0",
    "text.color":        "#e6f1ff",
    "grid.color":        "#2d3250",
    "grid.linestyle":    "--",
    "grid.alpha":        0.5,
})

TEAL    = "#64ffda"
RED     = "#ff6b6b"
YELLOW  = "#f8c555"
MUTED   = "#8892b0"
SURFACE = "#1e2130"


# ── Data helpers ──────────────────────────────────────────────────────────────
@st.cache_data(ttl=CACHE_TTL_SECONDS)
def load_data(slug: str) -> pd.DataFrame:
    init_db()
    with get_connection() as conn:
        df = pd.read_sql_query(
            "SELECT * FROM price_history WHERE product_slug=? ORDER BY date ASC",
            conn, params=(slug,),
        )
    df["date"] = pd.to_datetime(df["date"])
    return df


def trigger_update(slug: str) -> None:
    from update_price import update_product
    update_product(slug)
    st.cache_data.clear()


def reset_db() -> None:
    db = str(__import__("config").DB_PATH)
    if os.path.exists(db):
        os.remove(db)
    st.cache_data.clear()


# ── Chart helpers ─────────────────────────────────────────────────────────────
def _style_ax(ax, title: str = "") -> None:
    ax.grid(axis="y", alpha=0.4)
    ax.set_axisbelow(True)
    for spine in ax.spines.values():
        spine.set_edgecolor("#2d3250")
    if title:
        ax.set_title(title, color="#e6f1ff", fontsize=13, pad=12)


def render_price_chart(df: pd.DataFrame, product_name: str, mrp: float) -> None:
    hist_low  = df["price"].min()
    avg_price = df["price"].mean()

    fig, ax = plt.subplots(figsize=(13, 4.5))

    ax.fill_between(df["date"], df["price"], alpha=0.08, color=TEAL)
    ax.plot(df["date"], df["price"], color=TEAL,   linewidth=2,   label="Price", zorder=3)
    ax.axhline(hist_low,  color=RED,    linewidth=1.2, linestyle="--", label=f"All-time Low ₹{hist_low:,.0f}")
    ax.axhline(avg_price, color=YELLOW, linewidth=1.2, linestyle=":",  label=f"Average ₹{avg_price:,.0f}")
    ax.axhline(mrp,       color=MUTED,  linewidth=0.8, linestyle="-.", alpha=0.5, label=f"MRP ₹{mrp:,.0f}")

    # Highlight local minima (deals)
    window = max(3, len(df) // 20)
    local_min = df["price"][(df["price"].shift(window) > df["price"]) &
                            (df["price"].shift(-window) > df["price"])]
    ax.scatter(df.loc[local_min.index, "date"], local_min,
               color=TEAL, s=40, zorder=4, alpha=0.7)

    ax.xaxis.set_major_formatter(mdates.DateFormatter("%d %b"))
    ax.xaxis.set_major_locator(mdates.WeekdayLocator(interval=1))
    ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f"₹{x:,.0f}"))
    plt.xticks(rotation=30, fontsize=9)
    plt.yticks(fontsize=9)
    ax.set_ylabel("Price", color=MUTED, fontsize=10)
    ax.legend(facecolor=SURFACE, labelcolor="#e6f1ff", fontsize=9, framealpha=0.9)
    _style_ax(ax, f"{product_name} — Price History")

    plt.tight_layout()
    st.pyplot(fig, use_container_width=True)
    plt.close(fig)


def render_discount_chart(df: pd.DataFrame) -> None:
    fig, ax = plt.subplots(figsize=(10, 4))

    n, bins, patches = ax.hist(df["discount_percent"], bins=25,
                                color=TEAL, edgecolor="#0f1117", alpha=0.85)
    # Colour bars above threshold green, below red
    threshold = 30.0
    for patch, left in zip(patches, bins[:-1]):
        patch.set_facecolor(TEAL if left >= threshold else "#2d3250")

    ax.axvline(threshold, color=RED, linewidth=1.8, linestyle="--",
               label=f"{threshold:.0f}% deal threshold")
    ax.set_xlabel("Discount (%)", fontsize=10)
    ax.set_ylabel("Days",          fontsize=10)
    ax.legend(facecolor=SURFACE, labelcolor="#e6f1ff", fontsize=9)
    _style_ax(ax, "Discount Distribution")

    plt.tight_layout()
    st.pyplot(fig, use_container_width=True)
    plt.close(fig)


def render_rolling_avg_chart(df: pd.DataFrame) -> None:
    roll7  = df["price"].rolling(7,  min_periods=1).mean()
    roll30 = df["price"].rolling(30, min_periods=1).mean()

    fig, ax = plt.subplots(figsize=(13, 4))
    ax.plot(df["date"], df["price"], color=TEAL,   alpha=0.35, linewidth=1, label="Daily price")
    ax.plot(df["date"], roll7,       color=YELLOW,  linewidth=2,   label="7-day avg")
    ax.plot(df["date"], roll30,      color="#c084fc", linewidth=2,  linestyle="--", label="30-day avg")
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%d %b"))
    ax.xaxis.set_major_locator(mdates.WeekdayLocator(interval=1))
    ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f"₹{x:,.0f}"))
    plt.xticks(rotation=30, fontsize=9)
    ax.legend(facecolor=SURFACE, labelcolor="#e6f1ff", fontsize=9)
    _style_ax(ax, "Rolling Averages (7-day & 30-day)")

    plt.tight_layout()
    st.pyplot(fig, use_container_width=True)
    plt.close(fig)


# ── Sidebar ───────────────────────────────────────────────────────────────────
def render_sidebar(slug: str) -> tuple[str, bool]:
    with st.sidebar:
        st.markdown("## 🏷️ BestPrice")
        st.caption("AI-powered price tracker")

        st.markdown('<p class="sidebar-header">📦 Product</p>', unsafe_allow_html=True)
        product_options = {v.name: k for k, v in PRODUCTS.items()}
        current_name    = PRODUCTS[slug].name
        selected_name   = st.selectbox(
            "Select product", list(product_options.keys()),
            index=list(product_options.keys()).index(current_name),
            label_visibility="collapsed",
        )
        selected_slug = product_options[selected_name]

        st.markdown('<p class="sidebar-header">⚙️ Actions</p>', unsafe_allow_html=True)
        col1, col2 = st.columns(2)
        refresh = col1.button("🔄 Update", use_container_width=True,
                              help="Simulate / fetch today's price")
        reset   = col2.button("🗑️ Reset",  use_container_width=True,
                              help="Wipe ALL data and re-seed")

        if reset:
            reset_db()
            st.rerun()

        st.markdown('<p class="sidebar-header">📊 Data</p>', unsafe_allow_html=True)
        product = PRODUCTS[selected_slug]
        st.metric("MRP", f"₹{product.mrp:,.0f}")
        st.metric("Products tracked", len(PRODUCTS))

        st.markdown('<p class="sidebar-header">🔔 Alerts</p>', unsafe_allow_html=True)
        from config import ALERT_EMAIL_TO, ALERT_WEBHOOK_URL
        if ALERT_EMAIL_TO:
            st.success(f"✉️ Email → {ALERT_EMAIL_TO[:20]}…")
        else:
            st.info("Email alerts: not configured\nSet `ALERT_EMAIL_TO` in .env")
        if ALERT_WEBHOOK_URL:
            st.success("🔗 Webhook configured")
        else:
            st.info("Webhook alerts: not configured\nSet `ALERT_WEBHOOK_URL` in .env")

        st.markdown("---")
        st.caption("v2.0.0 · [GitHub](https://github.com/gunwant23/BestPrice) · MIT")

    return selected_slug, refresh


# ── Main ──────────────────────────────────────────────────────────────────────
def main() -> None:
    slug    = st.query_params.get("product", DEFAULT_PRODUCT_SLUG)
    slug, do_refresh = render_sidebar(slug)
    st.query_params["product"] = slug

    product = PRODUCTS[slug]

    if do_refresh:
        with st.spinner("Fetching latest price…"):
            trigger_update(slug)
        st.rerun()

    st.title(f"🏷️ BestPrice — {product.name}")
    st.caption(f"Tracking **{product.name}** · MRP {product.currency}{product.mrp:,.0f}")

    df = load_data(slug)

    if df.empty:
        st.warning("No data yet — click **🔄 Update** in the sidebar to get started.")
        return

    latest     = df.iloc[-1]
    current    = latest["price"]
    discount   = latest["discount_percent"]
    hist_low   = df["price"].min()
    hist_high  = df["price"].max()
    avg_price  = df["price"].mean()
    last_upd   = latest["date"].strftime("%d %b %Y, %I:%M %p")
    saving     = product.mrp - current

    prediction = predict_bargain(
        discount_percent=discount,
        historical_low=hist_low,
        current_price=current,
        mrp=product.mrp,
        product_slug=slug,
    )
    is_deal = prediction.is_good_deal

    # ── KPI cards ─────────────────────────────────────────────────────────────
    c1, c2, c3, c4, c5 = st.columns(5)
    cards = [
        (c1, "Current Price",   f"{product.currency}{current:,.0f}", f"Updated {last_upd}"),
        (c2, "Discount",        f"{discount:.1f}%",                  f"off MRP {product.currency}{product.mrp:,.0f}"),
        (c3, "You Save",        f"{product.currency}{saving:,.0f}",  "vs MRP"),
        (c4, "All-Time Low",    f"{product.currency}{hist_low:,.0f}", f"over {len(df)} records"),
        (c5, "Avg Price",       f"{product.currency}{avg_price:,.0f}", "60-day average"),
    ]
    for col, label, value, sub in cards:
        with col:
            st.markdown(
                f'<div class="metric-card">'
                f'<div class="label">{label}</div>'
                f'<div class="value">{value}</div>'
                f'<div class="sub">{sub}</div>'
                f'</div>',
                unsafe_allow_html=True,
            )

    st.markdown("<br>", unsafe_allow_html=True)

    # ── Verdict ───────────────────────────────────────────────────────────────
    badge_cls = "good" if is_deal else "bad"
    col_a, col_b = st.columns([1, 2])

    with col_a:
        st.markdown(
            f'<div class="deal-badge {badge_cls}">{prediction.verdict}</div>',
            unsafe_allow_html=True,
        )
        st.caption(f"**Method:** {prediction.method} · **Confidence:** {prediction.confidence_pct}")
        st.caption(f"**Why:** {prediction.reason}")

    with col_b:
        score = prediction.deal_score
        st.markdown(f"**Deal Score: {score}/100** {'(≥ 60 = good deal)' if score < 60 else '🎉'}")
        st.progress(score / 100)

        # Price position gauge
        pct_of_range = (current - hist_low) / max(hist_high - hist_low, 1)
        st.markdown(f"**Price Position** (0% = cheapest ever, 100% = most expensive ever)")
        st.progress(pct_of_range)
        st.caption(f"Currently at {pct_of_range * 100:.0f}% of historical range")

    st.divider()

    # ── Tabs ──────────────────────────────────────────────────────────────────
    tab1, tab2, tab3, tab4 = st.tabs([
        "📈 Price History",
        "📉 Rolling Averages",
        "📊 Discount Distribution",
        "🔍 Statistics",
    ])

    with tab1:
        render_price_chart(df, product.name, product.mrp)

    with tab2:
        if len(df) >= 7:
            render_rolling_avg_chart(df)
        else:
            st.info("Need at least 7 records for rolling averages. Click Update a few more times.")

    with tab3:
        render_discount_chart(df)

    with tab4:
        col1, col2 = st.columns(2)

        with col1:
            st.markdown("#### 📋 Price Statistics")
            stats_df = pd.DataFrame({
                "Metric": [
                    "Current Price", "MRP", "All-Time Low", "All-Time High",
                    "Average Price", "Median Price", "Std Deviation",
                ],
                "Value": [
                    f"{product.currency}{current:,.2f}",
                    f"{product.currency}{product.mrp:,.2f}",
                    f"{product.currency}{hist_low:,.2f}",
                    f"{product.currency}{hist_high:,.2f}",
                    f"{product.currency}{avg_price:,.2f}",
                    f"{product.currency}{df['price'].median():,.2f}",
                    f"{product.currency}{df['price'].std():,.2f}",
                ],
            })
            st.dataframe(stats_df, hide_index=True, use_container_width=True)

        with col2:
            st.markdown("#### 🎯 Deal Analytics")
            good_deals = (df["discount_percent"] >= 30).sum()
            pct        = good_deals / len(df) * 100
            st.metric("Days at ≥ 30% discount",   f"{good_deals} / {len(df)}")
            st.metric("Bargain frequency",         f"{pct:.1f}%")
            st.metric("Best discount ever",        f"{df['discount_percent'].max():.1f}%")
            st.metric("Best price ever",           f"{product.currency}{hist_low:,.0f}")
            st.metric("Total records",             len(df))

        st.markdown("#### 🕒 Recent Price History")
        recent = df.sort_values("date", ascending=False).head(15).copy()
        recent["date"]             = recent["date"].dt.strftime("%d %b %Y %H:%M")
        recent["price"]            = recent["price"].map(f"{product.currency}{{:,.2f}}".format)
        recent["discount_percent"] = recent["discount_percent"].map("{:.1f}%".format)
        st.dataframe(
            recent[["date", "price", "discount_percent"]].rename(
                columns={"date": "Date", "price": "Price", "discount_percent": "Discount"}
            ),
            hide_index=True,
            use_container_width=True,
        )

        # Download button
        csv = df.to_csv(index=False).encode("utf-8")
        st.download_button(
            "⬇️ Download Full History (CSV)",
            data=csv,
            file_name=f"{slug}_price_history.csv",
            mime="text/csv",
        )

    st.divider()
    st.caption(
        f"Last update: {last_upd} · {len(df)} records · "
        f"Model: {prediction.method} · "
        f"Confidence: {prediction.confidence_pct}"
    )


if __name__ == "__main__":
    main()
