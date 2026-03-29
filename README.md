# 🏷️ BestPrice — Single Product Price Tracker

> Track one product's price over time and get an instant AI-powered verdict: **Buy now or wait?**

![Python](https://img.shields.io/badge/Python-3.11-blue?logo=python)
![Streamlit](https://img.shields.io/badge/Streamlit-1.32-red?logo=streamlit)
![SQLite](https://img.shields.io/badge/Database-SQLite-lightgrey?logo=sqlite)
![License](https://img.shields.io/badge/License-MIT-green)

---

## 📸 Features

| Feature | Details |
|---------|---------|
| 📈 Price trend chart | 60-day line chart with rolling average |
| 📊 Discount histogram | See how often real deals happen |
| 🤖 Bargain detection | Rule-based + optional Logistic Regression |
| 🔁 Auto-update | Cron / GitHub Actions runs daily at midnight UTC |
| 🗄️ SQLite storage | Zero-config, serverless, version-control-friendly |

---

## 🚀 Quickstart (Local)

```bash
# 1. Clone the repo
git clone https://github.com/<you>/BestPrice.git
cd BestPrice

# 2. Create virtual env (recommended)
python -m venv .venv
source .venv/bin/activate      # Windows: .venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Launch the dashboard
streamlit run app.py
```

Open your browser at **http://localhost:8501**.  
Click **"Simulate Today's Price"** if the chart is empty.

---

## 🗄️ Database

SQLite file: `database.db` (auto-created on first run)

```sql
CREATE TABLE price_history (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    product_name     TEXT    NOT NULL,
    price            REAL    NOT NULL,
    mrp              REAL    NOT NULL,
    discount_percent REAL    NOT NULL,
    date             TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

The first run **seeds 60 days of realistic historical data** so charts look meaningful immediately.

---

## ⚙️ Scheduler Setup

### Option A — Local cron (Linux / macOS)

```bash
crontab -e
# Add this line (runs at midnight every day):
0 0 * * * cd /path/to/BestPrice && /path/to/.venv/bin/python update_price.py >> price_update.log 2>&1
```

### Option B — GitHub Actions (cloud, zero cost)

The file `.github/workflows/update_price.yml` is already configured.

1. Push this repo to GitHub.
2. The action runs every day at **00:00 UTC**.
3. It commits the updated `database.db` back to the repo automatically.
4. You can also trigger it manually from the **Actions → Run workflow** button.

> **Tip:** For Streamlit Cloud deployment, the `database.db` committed by GitHub Actions is what the app reads.

---

## 🌐 Deployment (Streamlit Cloud) — Free Tier

1. Push your repo to **GitHub** (make `database.db` is committed).
2. Go to [share.streamlit.io](https://share.streamlit.io) and click **New app**.
3. Select your repo → branch `main` → file `app.py`.
4. Click **Deploy** — live in ~60 seconds.

The GitHub Actions workflow keeps `database.db` updated daily, and Streamlit Cloud auto-redeploys on every push.

---

## 🤖 Model Explanation

`model.py` uses a **two-tier system**:

1. **Rule-based** (always active):
   - Discount ≥ 30 % of MRP → ✅ Good Deal
   - Price within 5 % of all-time low → ✅ Good Deal

2. **Logistic Regression** (activates when ≥ 10 records exist + scikit-learn is installed):
   - Trained on historical `(discount_percent, price/mrp)` pairs.
   - Outputs a probability score shown as Confidence %.

---

## 📁 Project Structure

```
BestPrice/
├── app.py              ← Streamlit dashboard
├── update_price.py     ← Daily price simulation
├── model.py            ← Bargain classifier
├── database.py         ← SQLite schema + seed
├── database.db         ← Auto-generated (commit this!)
├── requirements.txt
├── README.md
└── .github/
    └── workflows/
        └── update_price.yml  ← GitHub Actions scheduler
```

---

## ⚠️ Why No Flipkart Scraping?

Flipkart (and most large e-commerce sites) actively block scrapers:
- Dynamic JS rendering (Selenium required, slow and expensive)
- Anti-bot CAPTCHA and IP banning
- No public API

This project uses **realistic price simulation** instead — demonstrating all the ML, visualization, and scheduling concepts without the fragility of web scraping.

---

## 📄 License

MIT — use freely, star if useful ⭐
