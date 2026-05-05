# ── Build stage ────────────────────────────────────────────────────────────────
FROM python:3.11-slim AS builder

WORKDIR /app

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
        gcc \
        libffi-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --upgrade pip \
    && pip install --prefix=/install --no-cache-dir -r requirements.txt


# ── Runtime stage ──────────────────────────────────────────────────────────────
FROM python:3.11-slim AS runtime

LABEL maintainer="BestPrice <https://github.com/gunwant23/BestPrice>"
LABEL description="AI-powered product price tracker"
LABEL version="2.0.0"

# Non-root user for security
RUN groupadd -r bestprice && useradd -r -g bestprice bestprice

WORKDIR /app

# Copy installed packages from builder
COPY --from=builder /install /usr/local

# Copy application source
COPY --chown=bestprice:bestprice . .

# Streamlit config directory
RUN mkdir -p /app/.streamlit && chown -R bestprice:bestprice /app

# Data volume — mount external storage here to persist the SQLite DB
VOLUME ["/app/data"]

ENV BESTPRICE_DB_PATH=/app/data/database.db \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

USER bestprice

EXPOSE 8501

HEALTHCHECK --interval=30s --timeout=10s --start-period=20s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8501/_stcore/health')"

CMD ["streamlit", "run", "app.py", \
     "--server.port=8501", \
     "--server.address=0.0.0.0", \
     "--server.headless=true", \
     "--server.fileWatcherType=none", \
     "--browser.gatherUsageStats=false"]
