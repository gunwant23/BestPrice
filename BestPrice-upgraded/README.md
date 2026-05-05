# 🏷️ BestPrice — AI-Powered Product Price Tracker

<div align="center">

![Python](https://img.shields.io/badge/Python-3.10%2B-blue?logo=python&logoColor=white)
![Streamlit](https://img.shields.io/badge/Streamlit-1.35+-red?logo=streamlit&logoColor=white)
![SQLite](https://img.shields.io/badge/Database-SQLite-lightgrey?logo=sqlite)
![Docker](https://img.shields.io/badge/Docker-Ready-2496ED?logo=docker&logoColor=white)
![CI](https://img.shields.io/github/actions/workflow/status/gunwant23/BestPrice/ci.yml?label=CI&logo=github-actions)
![License](https://img.shields.io/badge/License-MIT-green)

**Track Indian e-commerce prices over time and get an instant AI verdict: Buy now, or wait?**

[Live Demo](https://share.streamlit.io) · [Report Bug](https://github.com/gunwant23/BestPrice/issues) · [Request Feature](https://github.com/gunwant23/BestPrice/issues)

</div>

---

## ✨ Features

| Feature | Details |
|---|---|
| 📦 **Multi-product tracking** | Track multiple products; switch via sidebar selector |
| 📈 **Price history charts** | 60-day line chart with area fill + deal markers |
| 📉 **Rolling averages** | 7-day and 30-day moving averages tab |
| 📊 **Discount histogram** | Visual distribution of how often deals occur |
| 🤖 **AI bargain detection** | Rule-based + Logistic Regression classifier |
| 🔔 **Alerts** | Email (SMTP) + Discord / Slack webhook notifications |
| 🕷️ **Scraper scaffold** | Flipkart & Amazon scrapers with simulation fallback |
| 📥 **CSV export** | Download full price history with one click |
| 🐳 **Docker ready** | Multi-stage Dockerfile + Docker Compose |
| ⚙️ **GitHub Actions** | CI (lint + test + coverage), daily updater, Docker push |
| 🧪 **40+ tests** | Pytest suite with full coverage across all modules |

---

## 🏗️ Architecture

```
BestPrice/
├── app.py              ← Streamlit dashboard (multi-tab, dark UI)
├── config.py           ← Single source of truth (products, thresholds, alerts)
├── database.py         ← SQLite schema, seeding, queries
├── model.py            ← Bargain classifier (rules + Logistic Regression)
├── scraper.py          ← Flipkart / Amazon scrapers + simulation fallback
├── alerts.py           ← Email + Discord/Slack webhook notifications
├── update_price.py     ← CLI daily price updater (--slug / --all)
├── requirements.txt
├── Dockerfile          ← Multi-stage, non-root, health-checked
├── docker-compose.yml  ← App + cron updater services
├── .env.example        ← All configurable env vars documented
├── .streamlit/
│   └── config.toml     ← Dark theme + performance settings
├── tests/
│   └── test_suite.py   ← 40+ pytest tests with fixtures & parametrize
└── .github/workflows/
    ├── ci.yml           ← Lint + test on Python 3.10 / 3.11 / 3.12
    ├── update_price.yml ← Daily price update + DB commit
    └── docker.yml       ← Build + push to GitHub Container Registry
```

---

## 🚀 Quickstart (Local)

### Prerequisites
- Python 3.10+
- Git

```bash
# 1. Clone
git clone https://github.com/gunwant23/BestPrice.git
cd BestPrice

# 2. Create virtual environment
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Configure (optional)
cp .env.example .env
# Edit .env with your alert credentials if desired

# 5. Launch dashboard
streamlit run app.py
```

Open **http://localhost:8501** in your browser.  
The app auto-seeds 60 days of realistic data on first run.

---

## 🐳 Docker

### One-command start
```bash
docker compose up -d
```

This starts two services:
- **bestprice_app** — Streamlit dashboard on port `8501`
- **bestprice_updater** — runs `update_price.py --all` every 24 h

### Manual Docker run
```bash
docker build -t bestprice .
docker run -p 8501:8501 -v $(pwd)/data:/app/data bestprice
```

### With alert credentials
```bash
docker compose --env-file .env up -d
```

---

## 🌐 Deploy to Streamlit Cloud (Free)

1. Fork this repo to your GitHub account.
2. Go to [share.streamlit.io](https://share.streamlit.io) → **New app**.
3. Select your fork → branch `main` → file `app.py` → **Deploy**.
4. Add secrets in **App settings → Secrets** (mirror your `.env`).

The GitHub Actions workflow (`update_price.yml`) commits `database.db` daily, and Streamlit Cloud auto-redeploys on every push — giving you a live-updated dashboard at zero cost.

---

## ⚙️ Configuration

All settings are driven by environment variables (see `.env.example`):

| Variable | Default | Description |
|---|---|---|
| `BESTPRICE_DB_PATH` | `./database.db` | SQLite file location |
| `BESTPRICE_PRODUCT` | `samsung-m34` | Default product slug |
| `BARGAIN_THRESHOLD` | `30` | Min discount % for "good deal" |
| `ALERT_EMAIL_FROM` | — | Sender Gmail address |
| `ALERT_EMAIL_TO` | — | Recipient(s), comma-separated |
| `ALERT_SMTP_PASSWORD` | — | Gmail App Password |
| `ALERT_WEBHOOK_URL` | — | Discord or Slack webhook URL |

### Adding a new product

Edit `config.py`:
```python
PRODUCTS["iphone-15"] = Product(
    slug="iphone-15",
    name="Apple iPhone 15 128GB",
    mrp=79_900.0,
    url="https://www.flipkart.com/apple-iphone-15/...",  # optional
)
```

The sidebar selector and all charts update automatically.

---

## 🤖 ML Model

Two-tier classification in `model.py`:

**Tier 1 — Rule-based** (always active):
- Discount ≥ 30% of MRP → ✅ Good Deal
- Price within 5% of all-time low AND discount ≥ 10% → ✅ Good Deal

**Tier 2 — Logistic Regression** (activates when ≥ 20 records exist):
- Features: `discount_percent`, `price / MRP`, `price / max_price`
- Labels: deal if discount ≥ threshold OR price ≤ 20th percentile
- `StandardScaler` + `class_weight='balanced'` for imbalanced data
- Returns probability → `confidence` shown in the UI

---

## 🧪 Testing

```bash
# Run full test suite
pytest tests/ -v

# With coverage report
pytest tests/ -v --cov=. --cov-report=term-missing

# Lint
ruff check . --select=E,F,W,I
```

CI runs automatically on every push across Python 3.10, 3.11, and 3.12.

---

## 🔔 Alerts Setup

### Email (Gmail)
1. Enable 2FA on your Google account.
2. Create an **App Password** at [myaccount.google.com/apppasswords](https://myaccount.google.com/apppasswords).
3. Set `ALERT_EMAIL_FROM`, `ALERT_EMAIL_TO`, `ALERT_SMTP_PASSWORD` in `.env`.

### Discord
1. Open your server → **Settings → Integrations → Webhooks → New Webhook**.
2. Copy the URL and set `ALERT_WEBHOOK_URL` in `.env`.

### Slack
1. Go to [api.slack.com/apps](https://api.slack.com/apps) → **Create New App → From Scratch**.
2. Enable **Incoming Webhooks** and copy the URL.
3. Set `ALERT_WEBHOOK_URL` in `.env`.

---

## ⚠️ Why No Live Scraping by Default?

Flipkart and Amazon use dynamic JS rendering, CAPTCHAs, and aggressive anti-bot measures. The scraper scaffold in `scraper.py` shows how real scraping would work, but the app **falls back to realistic price simulation** by default so everything works out-of-the-box without fragility.

To enable real scraping:
1. Add the product URL in `config.py → PRODUCTS[slug].url`.
2. Optionally plug in a proxy service or Playwright for JS-rendered pages.

---

## 📄 License

MIT — use freely, ⭐ star if useful!

---

<div align="center">
Built with ❤️ in India · <a href="https://github.com/gunwant23/BestPrice">github.com/gunwant23/BestPrice</a>
</div>
