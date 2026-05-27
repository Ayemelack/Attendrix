import logging
import smtplib
import ssl
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Optional, Dict, Any


logger = logging.getLogger(__name__)


@dataclass
class EmailEnvelope:
    recipient_email: str
    recipient_name: str = ""
    subject: str = ""
    html_body: str = ""
    text_body: Optional[str] = None
    reply_to: str = ""
    headers: Dict[str, str] = field(default_factory=dict)
    tracking_id: str = ""


@dataclass
class SendResult:
    success: bool
    provider: str
    message: str = ""
    provider_response: Optional[Dict[str, Any]] = None
    status_code: Optional[int] = None


class BaseMailProvider(ABC):
    @abstractmethod
    def send(self, envelope: EmailEnvelope) -> SendResult:
        ...

    @abstractmethod
    def test_connection(self) -> SendResult:
        ...


class SMTPMailProvider(BaseMailProvider):
    def __init__(
        self,
        host: str,
        port: int = 587,
        username: str = "",
        password: str = "",
        use_tls: bool = True,
        from_email: str = "",
        from_name: str = "Attendrix",
        timeout: int = 30,
    ):
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.use_tls = use_tls
        self.from_email = from_email
        self.from_name = from_name
        self.timeout = timeout

    def _build_message(self, envelope: EmailEnvelope) -> MIMEMultipart:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = envelope.subject
        msg["From"] = f"{self.from_name} <{self.from_email}>"
        msg["To"] = (
            f"{envelope.recipient_name} <{envelope.recipient_email}>"
            if envelope.recipient_name
            else envelope.recipient_email
        )
        if envelope.reply_to:
            msg["Reply-To"] = envelope.reply_to
        if envelope.tracking_id:
            msg["Message-ID"] = (
                f"<attendrix-{envelope.tracking_id}@{self.host}>"
            )
        for key, value in envelope.headers.items():
            msg[key] = value

        msg.attach(MIMEText(envelope.html_body, "html"))
        if envelope.text_body:
            msg.attach(MIMEText(envelope.text_body, "plain"))

        return msg

    def send(self, envelope: EmailEnvelope) -> SendResult:
        try:
            msg = self._build_message(envelope)

            if self.use_tls:
                context = ssl.create_default_context()
                server = smtplib.SMTP(self.host, self.port, timeout=self.timeout)
                server.ehlo()
                server.starttls(context=context)
                server.ehlo()
            else:
                server = smtplib.SMTP(self.host, self.port, timeout=self.timeout)
                server.ehlo()

            if self.username:
                server.login(self.username, self.password)

            server.sendmail(self.from_email, [envelope.recipient_email], msg.as_string())
            server.quit()

            logger.info(
                "SMTP sent to=%s | subject=%s | host=%s:%s",
                envelope.recipient_email, envelope.subject, self.host, self.port,
            )

            return SendResult(
                success=True,
                provider="smtp",
                message="Email delivered via SMTP",
            )

        except smtplib.SMTPAuthenticationError as exc:
            logger.error("SMTP auth FAILED for %s: %s", envelope.recipient_email, exc)
            return SendResult(
                success=False,
                provider="smtp",
                message="SMTP authentication failed",
                status_code=exc.smtp_code,
            )

        except smtplib.SMTPRecipientsRefused as exc:
            logger.error("SMTP recipient REFUSED for %s: %s", envelope.recipient_email, exc)
            return SendResult(
                success=False,
                provider="smtp",
                message=f"Recipient refused: {exc.recipients}",
            )

        except (smtplib.SMTPException, ConnectionRefusedError, TimeoutError, OSError) as exc:
            logger.error("SMTP send FAILED for %s: %s", envelope.recipient_email, exc)
            return SendResult(
                success=False,
                provider="smtp",
                message=f"SMTP error: {exc}",
            )

    def test_connection(self) -> SendResult:
        try:
            if self.use_tls:
                context = ssl.create_default_context()
                server = smtplib.SMTP(self.host, self.port, timeout=15)
                server.ehlo()
                server.starttls(context=context)
                server.ehlo()
            else:
                server = smtplib.SMTP(self.host, self.port, timeout=15)
                server.ehlo()

            if self.username:
                server.login(self.username, self.password)
            server.quit()

            logger.info("SMTP connection test PASSED: %s:%s", self.host, self.port)
            return SendResult(
                success=True,
                provider="smtp",
                message=f"SMTP {self.host}:{self.port} authenticated successfully",
            )

        except Exception as exc:
            logger.error("SMTP connection test FAILED: %s:%s — %s", self.host, self.port, exc)
            return SendResult(
                success=False,
                provider="smtp",
                message=f"SMTP connection failed: {exc}",
            )


class ResendMailProvider(BaseMailProvider):
    def __init__(
        self,
        api_key: str,
        from_email: str = "",
        from_name: str = "Attendrix",
    ):
        self.api_key = api_key
        self.from_email = from_email
        self.from_name = from_name

    def send(self, envelope: EmailEnvelope) -> SendResult:
        try:
            import requests
        except ImportError:
            return SendResult(
                success=False,
                provider="resend",
                message="requests library required",
            )

        payload = {
            "from": f"{self.from_name} <{self.from_email}>",
            "to": [envelope.recipient_email],
            "subject": envelope.subject,
            "html": envelope.html_body,
        }
        if envelope.recipient_name:
            payload["to"] = [f"{envelope.recipient_name} <{envelope.recipient_email}>"]
        if envelope.reply_to:
            payload["reply_to"] = envelope.reply_to

        try:
            resp = requests.post(
                "https://api.resend.com/emails",
                json=payload,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                timeout=30,
            )

            if resp.status_code in (200, 201):
                resp_body = resp.json()
                logger.info(
                    "Resend ACCEPTED for=%s | id=%s", envelope.recipient_email, resp_body.get("id", ""),
                )
                return SendResult(
                    success=True,
                    provider="resend",
                    message="Email accepted by Resend",
                    provider_response=resp_body,
                    status_code=resp.status_code,
                )

            try:
                resp_body = resp.json()
            except Exception:
                resp_body = {"raw": resp.text[:1000]}

            logger.error(
                "Resend REJECTED for=%s | status=%s", envelope.recipient_email, resp.status_code,
            )
            error_msg = resp_body.get("message", resp_body.get("error", f"Resend returned {resp.status_code}"))
            return SendResult(
                success=False,
                provider="resend",
                message=error_msg,
                provider_response=resp_body,
                status_code=resp.status_code,
            )

        except Exception as exc:
            logger.error("Resend FAILED for=%s: %s", envelope.recipient_email, exc)
            return SendResult(
                success=False,
                provider="resend",
                message=f"Resend connection error: {exc}",
            )

    def test_connection(self) -> SendResult:
        if not self.api_key:
            return SendResult(success=False, provider="resend", message="API key not set")
        return SendResult(success=True, provider="resend", message="Resend API key configured")
