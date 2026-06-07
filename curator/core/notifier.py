"""Notification handling for Curator."""
import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Optional

from .config import CuratorConfig, NotificationConfig
from .db import Deal


def send_telegram_notification(config: NotificationConfig, message: str) -> bool:
    """Send a Telegram notification.

    Args:
        config: Notification configuration
        message: Message text to send

    Returns:
        True if sent successfully, False otherwise
    """
    if not config.telegram_enabled:
        return False

    if not config.telegram_bot_token or not config.telegram_chat_id:
        return False

    try:
        import requests

        url = f"https://api.telegram.org/bot{config.telegram_bot_token}/sendMessage"
        data = {
            "chat_id": config.telegram_chat_id,
            "text": message,
            "parse_mode": "HTML",
            "disable_web_page_preview": True,
        }

        response = requests.post(url, json=data, timeout=10)
        return response.status_code == 200

    except Exception as e:
        print(f"Telegram notification failed: {e}")
        return False


def send_email_notification(config: NotificationConfig, subject: str, body: str) -> bool:
    """Send an email notification.

    Args:
        config: Notification configuration
        subject: Email subject
        body: Email body (HTML)

    Returns:
        True if sent successfully, False otherwise
    """
    if not config.email_enabled:
        return False

    # Override config with environment variables if set
    smtp_user = os.getenv("SMTP_USER") or config.smtp_user
    smtp_pass = os.getenv("SMTP_PASS") or config.smtp_pass
    smtp_host = os.getenv("SMTP_HOST") or config.smtp_host
    email_to = smtp_user  # Send to the same email address

    if not smtp_user or not smtp_pass or not email_to:
        print("Email notification failed: Missing SMTP credentials in environment or config")
        return False

    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = smtp_user
        msg["To"] = email_to

        html_part = MIMEText(body, "html")
        msg.attach(html_part)

        with smtplib.SMTP(smtp_host, config.smtp_port) as server:
            server.starttls()
            server.login(smtp_user, smtp_pass)
            server.send_message(msg)

        print(f"Email sent successfully to {email_to}")
        return True

    except Exception as e:
        print(f"Email notification failed: {e}")
        return False


def format_deal_message(deal: Deal) -> str:
    """Format a deal as a notification message.

    Args:
        deal: The deal to format

    Returns:
        Formatted message string (HTML)
    """
    watchlist_badge = "⭐ WATCHLIST " if deal.watchlist_hit else ""

    message = f"{deal.icon} {watchlist_badge}<b>{deal.name}</b>\n"
    message += f"💰 {deal.discount_pct}% OFF — "
    message += f"<s>${deal.original_price:.2f}</s> → <b>${deal.sale_price:.2f}</b>\n"

    if deal.rating:
        message += f"⭐ Rating: {deal.rating}/10\n"

    message += f"🎮 {deal.genre}"
    if deal.mac:
        message += " • 🍎 Mac"

    message += f"\n📅 Found: {deal.found_at}"

    return message


def notify_deals(config: CuratorConfig, deals: list[Deal]) -> None:
    """Send notifications for new deals.

    Args:
        config: Main curator configuration
        deals: List of deals to notify about
    """
    if not deals:
        return

    notifications_config = config.notifications

    # Group deals by watchlist/regular
    watchlist_deals = [d for d in deals if d.watchlist_hit]
    regular_deals = [d for d in deals if not d.watchlist_hit]

    # Send Telegram notifications
    if notifications_config.telegram_enabled:
        # Send watchlist hits immediately
        for deal in watchlist_deals:
            message = format_deal_message(deal)
            send_telegram_notification(notifications_config, message)

        # Send regular deals as summary
        if regular_deals:
            summary = f"🎯 Found {len(regular_deals)} new deals:\n\n"
            for deal in regular_deals[:5]:  # Limit to 5 deals
                summary += format_deal_message(deal) + "\n\n"

            if len(regular_deals) > 5:
                summary += f"... and {len(regular_deals) - 5} more deals"

            send_telegram_notification(notifications_config, summary)

    # Send email digest
    if notifications_config.email_enabled:
        subject = f"Curator: {len(deals)} new deals found"

        body = "<html><body>"
        body += f"<h2>🎯 {len(deals)} New Deals</h2>"

        if watchlist_deals:
            body += "<h3>⭐ Watchlist Hits</h3>"
            for deal in watchlist_deals:
                body += "<div style='margin: 20px 0; padding: 15px; border-left: 4px solid #4CAF50;'>"
                body += format_deal_message(deal).replace("\n", "<br>")
                body += "</div>"

        if regular_deals:
            body += "<h3>📦 Other Deals</h3>"
            for deal in regular_deals:
                body += "<div style='margin: 20px 0; padding: 15px; border-left: 4px solid #2196F3;'>"
                body += format_deal_message(deal).replace("\n", "<br>")
                body += "</div>"

        body += "</body></html>"

        send_email_notification(notifications_config, subject, body)
