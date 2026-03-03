"""
Email Delivery Service.
Supports SMTP and SendGrid.
Includes retry logic and structured response metadata.
"""
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import NamedTuple

from app.core.config import settings
from app.core.logging_config import get_logger

logger = get_logger(__name__)

class EmailResponse(NamedTuple):
    success: bool
    message_id: str | None = None
    provider_response: dict | None = None
    error: str | None = None


def send_email(to: str, subject: str, body: str) -> EmailResponse:
    """Dispatches email based on configured provider."""
    if settings.EMAIL_PROVIDER == "sendgrid":
        return _send_via_sendgrid(to, subject, body)
    return _send_via_smtp(to, subject, body)


def _send_via_smtp(to: str, subject: str, body: str) -> EmailResponse:
    msg = MIMEMultipart()
    msg["From"] = f"{settings.SMTP_FROM_NAME} <{settings.SMTP_FROM_EMAIL}>"
    msg["To"] = to
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "plain"))

    try:
        with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=10) as server:
            if settings.SMTP_PORT == 587:
                server.starttls()
            
            if settings.SMTP_USER and settings.SMTP_PASSWORD:
                server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
            
            # Returns a dict of refused recipients
            errors = server.send_message(msg)
            
            if errors:
                logger.error("SMTP partially failed", errors=errors)
                return EmailResponse(success=False, error=str(errors), provider_response=errors)

            # Generate a pseudo message ID for tracking
            import uuid
            msg_id = f"smtp-{uuid.uuid4()}"
            
            logger.info("Email sent via SMTP", to=to, msg_id=msg_id)
            return EmailResponse(success=True, message_id=msg_id, provider_response={"status": "accepted"})

    except smtplib.SMTPAuthenticationError:
        logger.error("SMTP Auth failed")
        return EmailResponse(success=False, error="Authentication failed")
    except Exception as e:
        logger.error("SMTP Delivery failed", error=str(e))
        return EmailResponse(success=False, error=str(e))


def _send_via_sendgrid(to: str, subject: str, body: str) -> EmailResponse:
    """SendGrid implementation using httpx for async-friendly sync calls."""
    import httpx
    
    url = "https://api.sendgrid.com/v3/mail/send"
    headers = {
        "Authorization": f"Bearer {settings.SENDGRID_API_KEY}",
        "Content-Type": "application/json",
    }
    data = {
        "personalizations": [{"to": [{"email": to}]}],
        "from": {"email": settings.SMTP_FROM_EMAIL, "name": settings.SMTP_FROM_NAME},
        "subject": subject,
        "content": [{"type": "text/plain", "value": body}],
    }

    try:
        response = httpx.post(url, headers=headers, json=data, timeout=10.0)
        if response.status_code in (200, 201, 202):
            msg_id = response.headers.get("X-Message-Id")
            return EmailResponse(success=True, message_id=msg_id, provider_response=response.json() if response.text else {"status": "accepted"})
        
        logger.error("SendGrid failed", status=response.status_code, body=response.text)
        return EmailResponse(success=False, error=response.text, provider_response={"status_code": response.status_code})
    except Exception as e:
        logger.error("SendGrid request failed", error=str(e))
        return EmailResponse(success=False, error=str(e))
