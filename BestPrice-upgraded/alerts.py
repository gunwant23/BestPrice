"""
alerts.py — Price-drop notifications.

Supported channels
------------------
- Email  (via SMTP — works with Gmail App Passwords, SendGrid, etc.)
- Webhook (Discord / Slack / any JSON endpoint)

Configuration (via environment variables or .env):
    ALERT_EMAIL_FROM      sender address
    ALERT_EMAIL_TO        recipient address (comma-separated for multiple)
    ALERT_SMTP_HOST       default: smtp.gmail.com
    ALERT_SMTP_PORT       default: 587
    ALERT_SMTP_PASSWORD   app password
    ALERT_WEBHOOK_URL     Discord / Slack webhook URL
"""
from __future__ import annotations

import json
import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Optional

from config import (
    ALERT_EMAIL_FROM,
    ALERT_EMAIL_TO,
    ALERT_SMTP_HOST,
    ALERT_SMTP_PORT,
    ALERT_SMTP_PASSWORD,
    ALERT_WEBHOOK_URL,
    Product,
)

logger = logging.getLogger(__name__)


# ── Email ─────────────────────────────────────────────────────────────────────

def _send_email(subject: str, html_body: str) -> bool:
    """Send an HTML email; returns True on success."""
    if not all([ALERT_EMAIL_FROM, ALERT_EMAIL_TO, ALERT_SMTP_PASSWORD]):
        logger.info("[alerts] Email not configured — skipping.")
        return False

    recipients = [r.strip() for r in ALERT_EMAIL_TO.split(",")]

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"]    = ALERT_EMAIL_FROM
    msg["To"]      = ", ".join(recipients)
    msg.attach(MIMEText(html_body, "html"))

    try:
        with smtplib.SMTP(ALERT_SMTP_HOST, ALERT_SMTP_PORT) as server:
            server.ehlo()
            server.starttls()
            server.login(ALERT_EMAIL_FROM, ALERT_SMTP_PASSWORD)
            server.sendmail(ALERT_EMAIL_FROM, recipients, msg.as_string())
        logger.info("[alerts] Email sent to %s", recipients)
        return True
    except Exception as exc:
        logger.error("[alerts] Email failed: %s", exc)
        return False


# ── Webhook (Discord / Slack) ─────────────────────────────────────────────────

def _send_webhook(payload: dict) -> bool:
    """POST a JSON payload to the configured webhook URL."""
    if not ALERT_WEBHOOK_URL:
        logger.info("[alerts] Webhook not configured — skipping.")
        return False

    try:
        import urllib.request

        data = json.dumps(payload).encode()
        req  = urllib.request.Request(
            ALERT_WEBHOOK_URL,
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            ok = 200 <= resp.status < 300
        if ok:
            logger.info("[alerts] Webhook delivered.")
        return ok
    except Exception as exc:
        logger.error("[alerts] Webhook failed: %s", exc)
        return False


def _discord_payload(product: Product, price: float, discount: float, confidence: float) -> dict:
    """Build a Discord-compatible embed payload."""
    colour = 0x64FFDA if discount >= 30 else 0xFF6B6B
    return {
        "embeds": [{
            "title": f"🏷️ BestPrice Alert — {product.name}",
            "colour": colour,
            "fields": [
                {"name": "Current Price", "value": f"{product.currency}{price:,.2f}", "inline": True},
                {"name": "MRP",           "value": f"{product.currency}{product.mrp:,.2f}", "inline": True},
                {"name": "Discount",      "value": f"{discount:.1f}%", "inline": True},
                {"name": "You Save",      "value": f"{product.currency}{product.mrp - price:,.2f}", "inline": True},
                {"name": "ML Confidence", "value": f"{confidence * 100:.0f}%", "inline": True},
            ],
            "footer": {"text": "BestPrice — AI-Powered Price Tracker"},
        }]
    }


def _slack_payload(product: Product, price: float, discount: float) -> dict:
    """Build a Slack-compatible Block Kit payload."""
    return {
        "text": f"🏷️ *BestPrice Alert* — {product.name}",
        "blocks": [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": (
                        f"*{product.name}* is now at *{product.currency}{price:,.2f}* "
                        f"({discount:.1f}% off MRP {product.currency}{product.mrp:,.2f})\n"
                        f"You save *{product.currency}{product.mrp - price:,.2f}*!"
                    ),
                },
            }
        ],
    }


# ── Public API ────────────────────────────────────────────────────────────────

def notify_good_deal(
    product: Product,
    price: float,
    discount: float,
    confidence: float = 0.9,
) -> None:
    """
    Fire all configured notification channels when a good deal is detected.

    Call this from update_price.py after model.predict_bargain() returns True.
    """
    saving  = product.mrp - price
    subject = (
        f"🔥 Deal Alert: {product.name} is {discount:.1f}% OFF "
        f"— {product.currency}{price:,.0f}"
    )

    html_body = f"""
    <html><body style="font-family:sans-serif;background:#0f1117;color:#e6f1ff;padding:24px;">
      <h2 style="color:#64ffda;">🏷️ BestPrice Deal Alert</h2>
      <h3>{product.name}</h3>
      <table style="border-collapse:collapse;">
        <tr><td style="padding:6px 12px;color:#8892b0;">Current Price</td>
            <td style="padding:6px 12px;font-size:20px;font-weight:bold;">{product.currency}{price:,.2f}</td></tr>
        <tr><td style="padding:6px 12px;color:#8892b0;">MRP</td>
            <td style="padding:6px 12px;">{product.currency}{product.mrp:,.2f}</td></tr>
        <tr><td style="padding:6px 12px;color:#8892b0;">Discount</td>
            <td style="padding:6px 12px;color:#64ffda;font-weight:bold;">{discount:.1f}%</td></tr>
        <tr><td style="padding:6px 12px;color:#8892b0;">You Save</td>
            <td style="padding:6px 12px;color:#64ffda;">{product.currency}{saving:,.2f}</td></tr>
        <tr><td style="padding:6px 12px;color:#8892b0;">AI Confidence</td>
            <td style="padding:6px 12px;">{confidence * 100:.0f}%</td></tr>
      </table>
      <p style="color:#8892b0;font-size:12px;margin-top:24px;">
        Sent by BestPrice — AI-Powered Price Tracker
      </p>
    </body></html>
    """

    _send_email(subject, html_body)

    # Auto-detect Discord vs Slack from URL
    if ALERT_WEBHOOK_URL:
        if "discord.com" in ALERT_WEBHOOK_URL:
            _send_webhook(_discord_payload(product, price, discount, confidence))
        else:
            _send_webhook(_slack_payload(product, price, discount))


if __name__ == "__main__":
    # Quick smoke-test (will no-op if env vars not set)
    from config import PRODUCTS
    prod = list(PRODUCTS.values())[0]
    notify_good_deal(prod, price=15_500.0, discount=32.6, confidence=0.87)
    print("Alert test complete (check your email/webhook).")
