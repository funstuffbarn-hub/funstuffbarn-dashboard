"""
Email utilities for sending reports.
"""
import smtplib
import ssl
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from services.shared.config import get_settings
from services.shared.logging import get_logger

logger = get_logger(__name__)
settings = get_settings()


def send_report_email(
    to_email: str,
    subject: str,
    body: str,
    html_body: str | None = None,
    attachments: list[str] = None,
) -> bool:
    """
    Send report email via Gmail SMTP.
    
    Args:
        to_email: Recipient email
        subject: Email subject
        body: Plain text body
        html_body: Optional HTML body
        attachments: List of file paths to attach
    
    Returns:
        True if sent successfully, False otherwise
    """
    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = settings.GMAIL_USER
        msg["To"] = to_email

        # Attach plain text
        msg.attach(MIMEText(body, "plain", "utf-8"))

        # Attach HTML if provided
        if html_body:
            msg.attach(MIMEText(html_body, "html", "utf-8"))

        # Attach files
        if attachments:
            for filepath in attachments:
                with open(filepath, "rb") as f:
                    part = MIMEApplication(f.read(), Name=filepath.split("/")[-1])
                    part["Content-Disposition"] = f'attachment; filename="{filepath.split("/")[-1]}"'
                    msg.attach(part)

        # Send via SSL
        context = ssl.create_default_context()
        with smtplib.SMTP_SSL(settings.SMTP_HOST, settings.SMTP_PORT, context=context) as server:
            server.login(settings.GMAIL_USER, settings.GMAIL_PASSWORD)
            server.send_message(msg)

        logger.info(f"Report sent to {to_email}")
        return True

    except Exception as e:
        logger.error(f"Failed to send email: {e}", exc_info=True)
        return False


def send_report_email(
    to_email: str,
    subject: str,
    body: str,
    html_body: str | None = None,
) -> bool:
    """Convenience function for sending reports."""
    return send_report_email(to_email, subject, body, html_body)
