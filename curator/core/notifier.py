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

    # Check if this is a concert (has ticket_url in raw data)
    is_concert = deal.source == "ticketmaster" or "ticket_url" in deal.raw

    if is_concert:
        # Concert formatting
        message = f"{deal.icon} {watchlist_badge}<b>{deal.name}</b>\n"

        # Date and time
        date = deal.raw.get('date', 'TBA')
        time = deal.raw.get('time', '')
        if time:
            message += f"📅 {date} at {time}\n"
        else:
            message += f"📅 {date}\n"

        # Location
        location = deal.raw.get('location', 'Unknown')
        message += f"📍 {location}\n"

        # Ticket link
        ticket_url = deal.raw.get('ticket_url', '')
        if ticket_url:
            message += f"🎫 <a href='{ticket_url}'>Get Tickets</a>"
    else:
        # Game deal formatting
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


def notify_deals(config: CuratorConfig, deals: list[Deal], run_results: dict = None) -> None:
    """Send notifications for new deals or daily summary.

    Args:
        config: Main curator configuration
        deals: List of deals to notify about
        run_results: Dictionary of agent run results (optional)
    """
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

    # Send email digest (always send if email is enabled)
    if notifications_config.email_enabled:
        if deals:
            # Email with deals found
            subject = f"Curator: {len(deals)} new deals found"

            body = "<html><body>"
            body += f"<h2>🎯 {len(deals)} New Deals</h2>"

            # Group by agent type
            game_deals = [d for d in deals if d.agent_id == "steam"]
            concert_deals = [d for d in deals if d.agent_id == "concert"]

            # Watchlist hits (across all agents)
            if watchlist_deals:
                body += "<h3>⭐ Watchlist Hits</h3>"
                for deal in watchlist_deals:
                    body += "<div style='margin: 20px 0; padding: 15px; border-left: 4px solid #4CAF50;'>"
                    body += format_deal_message(deal).replace("\n", "<br>")
                    body += "</div>"

            # Game deals
            game_deals_no_watchlist = [d for d in game_deals if not d.watchlist_hit]
            if game_deals_no_watchlist:
                body += "<h3>🎮 Game Deals</h3>"
                for deal in game_deals_no_watchlist:
                    body += "<div style='margin: 20px 0; padding: 15px; border-left: 4px solid #2196F3;'>"
                    body += format_deal_message(deal).replace("\n", "<br>")
                    body += "</div>"

            # Concerts
            concert_deals_no_watchlist = [d for d in concert_deals if not d.watchlist_hit]
            if concert_deals_no_watchlist:
                body += "<h3>🎵 Concerts</h3>"
                for deal in concert_deals_no_watchlist:
                    body += "<div style='margin: 20px 0; padding: 15px; border-left: 4px solid #9C27B0;'>"
                    body += format_deal_message(deal).replace("\n", "<br>")
                    body += "</div>"

            body += "</body></html>"
        else:
            # Daily summary with no deals
            from datetime import datetime
            subject = f"Curator Daily Summary - {datetime.now().strftime('%Y-%m-%d')}"

            body = "<html><body>"
            body += "<h2>📊 Curator Daily Summary</h2>"
            body += "<p><strong>No new deals found today.</strong></p>"

            # Show run results if available
            if run_results:
                body += "<h3>Agent Status</h3>"
                body += "<table style='border-collapse: collapse; width: 100%;'>"
                body += "<tr style='background-color: #f2f2f2;'>"
                body += "<th style='padding: 8px; text-align: left; border: 1px solid #ddd;'>Agent</th>"
                body += "<th style='padding: 8px; text-align: left; border: 1px solid #ddd;'>Status</th>"
                body += "<th style='padding: 8px; text-align: left; border: 1px solid #ddd;'>Details</th>"
                body += "</tr>"

                for agent_id, result in run_results.items():
                    status = result.get("status", "unknown")
                    status_icon = "✅" if status == "success" else "❌"

                    details = ""
                    if status == "success":
                        items_fetched = result.get("items_fetched", 0)
                        deals_found = result.get("deals_found", 0)
                        details = f"{items_fetched} items checked, {deals_found} passed filters"
                    else:
                        details = result.get("error", "Unknown error")

                    body += f"<tr>"
                    body += f"<td style='padding: 8px; border: 1px solid #ddd;'>{agent_id}</td>"
                    body += f"<td style='padding: 8px; border: 1px solid #ddd;'>{status_icon} {status}</td>"
                    body += f"<td style='padding: 8px; border: 1px solid #ddd;'>{details}</td>"
                    body += "</tr>"

                body += "</table>"

            body += "<p style='margin-top: 20px; color: #666;'>Curator is running normally. You'll receive an email when new deals are found.</p>"
            body += "</body></html>"

        send_email_notification(notifications_config, subject, body)
