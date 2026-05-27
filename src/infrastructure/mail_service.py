import hashlib
import json
import logging
import os
import uuid
from datetime import datetime, timedelta
from string import Template
from typing import Optional, Dict, Any, List
from sqlalchemy import and_
from .sqlalchemy_db import get_db_session
from .mail_models import (
    MailQueue,
    MailTemplate,
    MailAuditLog,
    MailSmtpProfile,
    MailUnsubscribe,
    MailStatus,
    MailEventType,
    MailTemplateCategory,
    _utc_now,
)
from .mail_providers import (
    BaseMailProvider,
    SMTPMailProvider,
    ResendMailProvider,
    EmailEnvelope,
    SendResult,
)


logger = logging.getLogger(__name__)

TEMPLATES_DIR = os.path.join(os.path.dirname(__file__), "mail_templates")
BASE_LAYOUT_FILE = os.path.join(TEMPLATES_DIR, "base_layout.html")

CATEGORY_TEMPLATE_MAP = {
    MailTemplateCategory.VOUCHER_DELIVERY: "voucher_delivery.html",
    MailTemplateCategory.DEMO_CONFIRMATION: "demo_confirmation.html",
    MailTemplateCategory.PASSWORD_RESET: "password_reset.html",
    MailTemplateCategory.ACCOUNT_ACTIVATION: "account_activation.html",
    MailTemplateCategory.ATTENDANCE_NOTIFICATION: "attendance_notification.html",
    MailTemplateCategory.INSTITUTION_ANNOUNCEMENT: "institution_announcement.html",
    MailTemplateCategory.SYSTEM_ALERT: "system_alert.html",
}

UNSUBSCRIBE_SALT = os.environ.get("MAIL_UNSUBSCRIBE_SALT", "attendrix-mail-signing-key")


def _load_template_file(filename: str) -> str:
    filepath = os.path.join(TEMPLATES_DIR, filename)
    if not os.path.exists(filepath):
        logger.error("Template file not found: %s", filepath)
        return ""
    with open(filepath, "r", encoding="utf-8") as f:
        return f.read()


def _render_template(template_str: str, variables: Dict[str, Any]) -> str:
    if not template_str:
        return ""
    t = Template(template_str)
    safe_vars = {k: (v if v is not None else "") for k, v in variables.items()}
    try:
        return t.safe_substitute(safe_vars)
    except Exception as exc:
        logger.error("Template rendering error: %s", exc)
        return template_str


def _build_unsubscribe_token(recipient_email: str) -> str:
    raw = recipient_email + UNSUBSCRIBE_SALT
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _build_unsubscribe_url(recipient_email: str, app_url: str = "") -> str:
    token = _build_unsubscribe_token(recipient_email)
    base = app_url or os.environ.get("APP_URL", "http://localhost:5000")
    return f"{base}/api/mail/unsubscribe?token={token}&email_hash={hashlib.sha256(recipient_email.encode('utf-8')).hexdigest()}"


class MailService:
    def __init__(self):
        self._providers: Dict[str, BaseMailProvider] = {}
        self._initialized = False
        self._app_url = os.environ.get("APP_URL", "http://localhost:5000")

    def initialize(self):
        if self._initialized:
            return
        self._load_providers()
        self._seed_default_templates()
        self._initialized = True
        logger.info("MailService initialized with %d provider(s)", len(self._providers))

    def _load_providers(self):
        session = get_db_session()
        try:
            profiles = session.query(MailSmtpProfile).filter_by(is_active=True).all()
            for profile in profiles:
                provider = self._build_provider(profile)
                if provider:
                    self._providers[profile.id] = provider
                    logger.info(
                        "Loaded SMTP profile: %s (%s:%s)", profile.name, profile.host, profile.port,
                    )
            if not profiles:
                self._load_providers_from_env()
        except Exception as exc:
            logger.warning("Could not load SMTP profiles from DB: %s. Falling back to env.", exc)
            self._load_providers_from_env()
        finally:
            session.close()

    def _load_providers_from_env(self):
        smtp_host = os.environ.get("SMTP_HOST", "")
        smtp_user = os.environ.get("SMTP_USER", "")
        smtp_pass = os.environ.get("SMTP_PASS", "")
        smtp_port = int(os.environ.get("SMTP_PORT", "587"))
        smtp_tls = os.environ.get("SMTP_USE_TLS", "true").lower() == "true"
        from_email = os.environ.get("MAIL_FROM", os.environ.get("RESEND_FROM_EMAIL", "noreply@attendrix.com"))
        from_name = os.environ.get("MAIL_FROM_NAME", "Attendrix")

        resend_key = os.environ.get("RESEND_API_KEY", "")

        if smtp_host and smtp_user:
            provider = SMTPMailProvider(
                host=smtp_host,
                port=smtp_port,
                username=smtp_user,
                password=smtp_pass,
                use_tls=smtp_tls,
                from_email=from_email,
                from_name=from_name,
            )
            env_profile_id = "env:smtp"
            self._providers[env_profile_id] = provider
            logger.info("Loaded SMTP provider from env: %s:%s", smtp_host, smtp_port)
        elif resend_key:
            provider = ResendMailProvider(
                api_key=resend_key,
                from_email=from_email,
                from_name=from_name,
            )
            env_profile_id = "env:resend"
            self._providers[env_profile_id] = provider
            logger.info("Loaded Resend provider from env")
        else:
            logger.info("No email providers configured. Emails will be queued but not sent.")

    def _build_provider(self, profile: MailSmtpProfile) -> Optional[BaseMailProvider]:
        ptype = profile.provider_type or "smtp"
        if ptype == "smtp":
            return SMTPMailProvider(
                host=profile.host,
                port=profile.port,
                username=profile.username,
                password=profile.password,
                use_tls=profile.use_tls,
                from_email=profile.from_email,
                from_name=profile.from_name,
            )
        elif ptype == "resend":
            return ResendMailProvider(
                api_key=profile.password,
                from_email=profile.from_email,
                from_name=profile.from_name,
            )
        return None

    def _get_provider_for_template(self, template: MailTemplate) -> Optional[BaseMailProvider]:
        if template and template.smtp_profile_id and template.smtp_profile_id in self._providers:
            return self._providers[template.smtp_profile_id]

        primary_id = None
        session = get_db_session()
        try:
            primary = session.query(MailSmtpProfile).filter_by(is_primary=True, is_active=True).first()
            if primary:
                primary_id = primary.id
        except Exception:
            pass
        finally:
            session.close()

        if primary_id and primary_id in self._providers:
            return self._providers[primary_id]

        for pid, provider in self._providers.items():
            return provider

        return None

    def _get_default_provider(self) -> Optional[BaseMailProvider]:
        for pid, provider in self._providers.items():
            return provider
        return None

    def _seed_default_templates(self):
        session = get_db_session()
        try:
            existing = session.query(MailTemplate).count()
            if existing > 0:
                return

            for category, filename in CATEGORY_TEMPLATE_MAP.items():
                body = _load_template_file(filename)
                if not body:
                    continue

                default_subjects = {
                    MailTemplateCategory.VOUCHER_DELIVERY: "Your Attendrix $role_name Voucher Code",
                    MailTemplateCategory.DEMO_CONFIRMATION: "Your Attendrix Demo is Confirmed — $demo_date",
                    MailTemplateCategory.PASSWORD_RESET: "Reset Your Attendrix Password",
                    MailTemplateCategory.ACCOUNT_ACTIVATION: "Welcome to Attendrix — Activate Your Account",
                    MailTemplateCategory.ATTENDANCE_NOTIFICATION: "Attendance Recorded for $course_name",
                    MailTemplateCategory.INSTITUTION_ANNOUNCEMENT: "$announcement_title",
                    MailTemplateCategory.SYSTEM_ALERT: "System Alert: $alert_title",
                }

                variables_schema = {
                    MailTemplateCategory.VOUCHER_DELIVERY: ["recipient_name", "role_name", "voucher_code", "expires_at"],
                    MailTemplateCategory.DEMO_CONFIRMATION: ["recipient_name", "institution", "demo_date", "demo_time", "timezone", "portal_url"],
                    MailTemplateCategory.PASSWORD_RESET: ["recipient_name", "reset_link", "expiry_minutes"],
                    MailTemplateCategory.ACCOUNT_ACTIVATION: ["recipient_name", "recipient_email", "activation_link", "role_name", "institution_name"],
                    MailTemplateCategory.ATTENDANCE_NOTIFICATION: ["recipient_name", "course_name", "session_name", "session_date", "attendance_status", "status_color"],
                    MailTemplateCategory.INSTITUTION_ANNOUNCEMENT: ["recipient_name", "announcement_title", "announcement_body", "institution_name", "announcement_date"],
                    MailTemplateCategory.SYSTEM_ALERT: ["alert_title", "alert_message", "alert_severity", "alert_timestamp", "alert_component"],
                }

                template = MailTemplate(
                    id=str(uuid.uuid4()),
                    template_name=category.value,
                    category=category.value,
                    subject_template=default_subjects.get(category, ""),
                    body_template=body,
                    variables_schema=variables_schema.get(category),
                    is_active=True,
                )
                session.add(template)

            session.commit()
            logger.info("Seeded %d default email templates", len(CATEGORY_TEMPLATE_MAP))
        except Exception as exc:
            session.rollback()
            logger.error("Failed to seed default templates: %s", exc)
        finally:
            session.close()

    def queue_email(
        self,
        template_type: str,
        recipient_email: str,
        variables: Dict[str, Any],
        recipient_name: str = "",
        priority: int = 0,
        smtp_profile_id: Optional[str] = None,
    ) -> Optional[str]:
        session = get_db_session()
        try:
            template = (
                session.query(MailTemplate)
                .filter_by(template_name=template_type, is_active=True)
                .first()
            )
            if not template:
                logger.error("No active template found for type: %s", template_type)
                return None

            subject = _render_template(template.subject_template, variables)
            body_content = _render_template(template.body_template, variables)

            base_layout = _load_template_file("base_layout.html")
            unsubscribe_url = _build_unsubscribe_url(recipient_email, self._app_url)
            html_body = _render_template(
                base_layout,
                {
                    "subject": subject,
                    "body_content": body_content,
                    "unsubscribe_url": unsubscribe_url,
                },
            )

            profile_id = smtp_profile_id or template.smtp_profile_id

            mail_id = str(uuid.uuid4())
            now = _utc_now()

            mail = MailQueue(
                id=mail_id,
                template_id=template.id,
                smtp_profile_id=profile_id,
                recipient_email=recipient_email,
                recipient_name=recipient_name,
                subject=subject,
                body_html=html_body,
                status=MailStatus.PENDING.value,
                priority=priority,
                retry_count=0,
                max_retries=3,
                batch_id=str(uuid.uuid4()),
                template_type=template_type,
                created_at=now,
            )
            session.add(mail)

            audit = MailAuditLog(
                id=str(uuid.uuid4()),
                mail_id=mail_id,
                event_type=MailEventType.QUEUED.value,
                details={
                    "template_type": template_type,
                    "recipient_email": recipient_email,
                    "subject": subject,
                },
                created_at=now,
            )
            session.add(audit)
            session.commit()

            logger.info(
                "Email queued: id=%s | type=%s | to=%s | subject=%s",
                mail_id, template_type, recipient_email, subject,
            )
            return mail_id

        except Exception as exc:
            session.rollback()
            logger.error("Failed to queue email: %s", exc)
            return None
        finally:
            session.close()

    def process_queue(self, batch_size: int = 20) -> int:
        session = get_db_session()
        processed = 0
        try:
            now = _utc_now()
            mails = (
                session.query(MailQueue)
                .filter(
                    and_(
                        MailQueue.status.in_([
                            MailStatus.PENDING.value,
                            MailStatus.RETRYING.value,
                        ]),
                        (
                            MailQueue.next_retry_at.is_(None)
                            | (MailQueue.next_retry_at <= now)
                        ),
                    )
                )
                .order_by(MailQueue.priority.desc(), MailQueue.created_at.asc())
                .limit(batch_size)
                .all()
            )

            for mail in mails:
                try:
                    self._send_mail(session, mail)
                    processed += 1
                except Exception as exc:
                    logger.error("Failed to process mail %s: %s", mail.id, exc)
                    self._mark_failed(session, mail, str(exc))

            if mails:
                session.commit()
                logger.info("Mail queue processed: %d emails", len(mails))

        except Exception as exc:
            session.rollback()
            logger.error("Mail queue processing error: %s", exc)
        finally:
            session.close()

        return processed

    def _send_mail(self, session, mail: MailQueue):
        template = None
        if mail.template_id:
            template = session.query(MailTemplate).filter_by(id=mail.template_id).first()

        provider = None
        if mail.smtp_profile_id and mail.smtp_profile_id in self._providers:
            provider = self._providers[mail.smtp_profile_id]
        elif template:
            provider = self._get_provider_for_template(template)

        if not provider:
            provider = self._get_default_provider()

        if not provider:
            logger.warning("No provider available for mail %s. Skipping.", mail.id)
            self._mark_failed(session, mail, "No email provider configured")
            return

        mail.status = MailStatus.PROCESSING.value
        session.flush()

        envelope = EmailEnvelope(
            recipient_email=mail.recipient_email,
            recipient_name=mail.recipient_name or "",
            subject=mail.subject,
            html_body=mail.body_html,
            tracking_id=mail.tracking_id,
        )

        result = provider.send(envelope)

        if result.success:
            mail.status = MailStatus.SENT.value
            mail.sent_at = _utc_now()
            mail.smtp_response = result.message
            mail.error_message = None

            audit = MailAuditLog(
                id=str(uuid.uuid4()),
                mail_id=mail.id,
                event_type=MailEventType.SENT.value,
                details={
                    "provider": result.provider,
                    "message": result.message,
                    "provider_response": result.provider_response,
                },
                created_at=_utc_now(),
            )
            session.add(audit)
            logger.info("Email sent: id=%s | to=%s", mail.id, mail.recipient_email)
        else:
            mail.retry_count += 1
            mail.error_message = result.message

            if mail.retry_count >= mail.max_retries:
                mail.status = MailStatus.FAILED.value
                event_type = MailEventType.FAILED.value
                logger.error(
                    "Email FAILED after %d retries: id=%s | to=%s | error=%s",
                    mail.retry_count, mail.id, mail.recipient_email, result.message,
                )
            else:
                delay_seconds = min(60 * (2 ** (mail.retry_count - 1)), 3600 * 12)
                mail.status = MailStatus.RETRYING.value
                mail.next_retry_at = _utc_now() + timedelta(seconds=delay_seconds)
                event_type = MailEventType.RETRIED.value
                logger.warning(
                    "Email RETRYING: id=%s | attempt=%d/%d | delay=%ds | error=%s",
                    mail.id, mail.retry_count, mail.max_retries, delay_seconds, result.message,
                )

            audit = MailAuditLog(
                id=str(uuid.uuid4()),
                mail_id=mail.id,
                event_type=event_type,
                details={
                    "provider": result.provider,
                    "error": result.message,
                    "retry_count": mail.retry_count,
                    "max_retries": mail.max_retries,
                    "next_retry_at": mail.next_retry_at.isoformat() if mail.next_retry_at else None,
                },
                created_at=_utc_now(),
            )
            session.add(audit)

    def _mark_failed(self, session, mail: MailQueue, error: str):
        mail.status = MailStatus.FAILED.value
        mail.error_message = error
        mail.retry_count = (mail.retry_count or 0) + 1

        audit = MailAuditLog(
            id=str(uuid.uuid4()),
            mail_id=mail.id,
            event_type=MailEventType.FAILED.value,
            details={"error": error},
            created_at=_utc_now(),
        )
        session.add(audit)

    def retry_failed_emails(self, mail_ids: Optional[List[str]] = None) -> int:
        session = get_db_session()
        retried = 0
        try:
            query = session.query(MailQueue).filter(MailQueue.status == MailStatus.FAILED.value)
            if mail_ids:
                query = query.filter(MailQueue.id.in_(mail_ids))

            mails = query.all()
            now = _utc_now()

            for mail in mails:
                mail.status = MailStatus.RETRYING.value
                mail.retry_count = 0
                mail.next_retry_at = now
                mail.error_message = None

                audit = MailAuditLog(
                    id=str(uuid.uuid4()),
                    mail_id=mail.id,
                    event_type=MailEventType.RETRIED.value,
                    details={"action": "manual_retry", "previous_retry_count": mail.retry_count},
                    created_at=now,
                )
                session.add(audit)
                retried += 1

            session.commit()
            logger.info("Retry queued for %d failed emails", retried)
        except Exception as exc:
            session.rollback()
            logger.error("Failed to queue retry: %s", exc)
        finally:
            session.close()

        return retried

    def cancel_email(self, mail_id: str) -> bool:
        session = get_db_session()
        try:
            mail = session.query(MailQueue).filter_by(id=mail_id).first()
            if not mail or mail.status in (MailStatus.SENT.value, MailStatus.CANCELLED.value):
                return False

            old_status = mail.status
            mail.status = MailStatus.CANCELLED.value

            audit = MailAuditLog(
                id=str(uuid.uuid4()),
                mail_id=mail_id,
                event_type=MailEventType.CANCELLED.value,
                details={"previous_status": old_status},
                created_at=_utc_now(),
            )
            session.add(audit)
            session.commit()
            return True
        except Exception as exc:
            session.rollback()
            logger.error("Failed to cancel mail %s: %s", mail_id, exc)
            return False
        finally:
            session.close()

    def log_mail_event(
        self,
        mail_id: str,
        event_type: str,
        details: Optional[Dict[str, Any]] = None,
    ) -> bool:
        session = get_db_session()
        try:
            audit = MailAuditLog(
                id=str(uuid.uuid4()),
                mail_id=mail_id,
                event_type=event_type,
                details=details or {},
                created_at=_utc_now(),
            )
            session.add(audit)
            session.commit()
            return True
        except Exception as exc:
            session.rollback()
            logger.error("Failed to log mail event: %s", exc)
            return False
        finally:
            session.close()

    def get_queue_stats(self) -> Dict[str, Any]:
        session = get_db_session()
        try:
            total = session.query(MailQueue).count()
            pending = session.query(MailQueue).filter(MailQueue.status == MailStatus.PENDING.value).count()
            processing = session.query(MailQueue).filter(MailQueue.status == MailStatus.PROCESSING.value).count()
            sent = session.query(MailQueue).filter(MailQueue.status == MailStatus.SENT.value).count()
            failed = session.query(MailQueue).filter(MailQueue.status == MailStatus.FAILED.value).count()
            retrying = session.query(MailQueue).filter(MailQueue.status == MailStatus.RETRYING.value).count()
            cancelled = session.query(MailQueue).filter(MailQueue.status == MailStatus.CANCELLED.value).count()

            now = _utc_now()
            today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
            sent_today = session.query(MailQueue).filter(
                MailQueue.status == MailStatus.SENT.value,
                MailQueue.sent_at >= today_start,
            ).count()
            failed_today = session.query(MailQueue).filter(
                MailQueue.status == MailStatus.FAILED.value,
                MailQueue.created_at >= today_start,
            ).count()

            return {
                "total": total,
                "pending": pending,
                "processing": processing,
                "sent": sent,
                "failed": failed,
                "retrying": retrying,
                "cancelled": cancelled,
                "sent_today": sent_today,
                "failed_today": failed_today,
            }
        except Exception as exc:
            logger.error("Failed to get queue stats: %s", exc)
            return {}
        finally:
            session.close()

    def get_templates(self) -> List[Dict[str, Any]]:
        session = get_db_session()
        try:
            templates = session.query(MailTemplate).order_by(MailTemplate.category).all()
            return [
                {
                    "id": t.id,
                    "template_name": t.template_name,
                    "category": t.category,
                    "subject_template": t.subject_template,
                    "is_active": t.is_active,
                    "created_at": t.created_at.isoformat() if t.created_at else None,
                    "updated_at": t.updated_at.isoformat() if t.updated_at else None,
                }
                for t in templates
            ]
        except Exception as exc:
            logger.error("Failed to get templates: %s", exc)
            return []
        finally:
            session.close()

    def get_audit_logs(self, limit: int = 100) -> List[Dict[str, Any]]:
        session = get_db_session()
        try:
            logs = (
                session.query(MailAuditLog)
                .order_by(MailAuditLog.created_at.desc())
                .limit(limit)
                .all()
            )
            return [
                {
                    "id": log.id,
                    "mail_id": log.mail_id,
                    "event_type": log.event_type,
                    "details": log.details,
                    "created_at": log.created_at.isoformat() if log.created_at else None,
                }
                for log in logs
            ]
        except Exception as exc:
            logger.error("Failed to get audit logs: %s", exc)
            return []
        finally:
            session.close()

    def get_queue_emails(
        self, status_filter: Optional[str] = None, limit: int = 50
    ) -> List[Dict[str, Any]]:
        session = get_db_session()
        try:
            query = session.query(MailQueue).order_by(MailQueue.created_at.desc())
            if status_filter:
                query = query.filter(MailQueue.status == status_filter)
            mails = query.limit(limit).all()
            return [
                {
                    "id": m.id,
                    "recipient_email": m.recipient_email,
                    "recipient_name": m.recipient_name,
                    "subject": m.subject,
                    "status": m.status,
                    "template_type": m.template_type,
                    "retry_count": m.retry_count,
                    "max_retries": m.max_retries,
                    "error_message": m.error_message,
                    "created_at": m.created_at.isoformat() if m.created_at else None,
                    "sent_at": m.sent_at.isoformat() if m.sent_at else None,
                    "next_retry_at": m.next_retry_at.isoformat() if m.next_retry_at else None,
                }
                for m in mails
            ]
        except Exception as exc:
            logger.error("Failed to get queue emails: %s", exc)
            return []
        finally:
            session.close()

    def get_mail_status(self, mail_id: str) -> Optional[Dict[str, Any]]:
        session = get_db_session()
        try:
            m = session.query(MailQueue).filter_by(id=mail_id).first()
            if not m:
                return None
            return {
                "id": m.id,
                "recipient_email": m.recipient_email,
                "recipient_name": m.recipient_name,
                "subject": m.subject,
                "status": m.status,
                "template_type": m.template_type,
                "retry_count": m.retry_count,
                "max_retries": m.max_retries,
                "error_message": m.error_message,
                "created_at": m.created_at.isoformat() if m.created_at else None,
                "sent_at": m.sent_at.isoformat() if m.sent_at else None,
                "next_retry_at": m.next_retry_at.isoformat() if m.next_retry_at else None,
            }
        except Exception as exc:
            logger.error("Failed to get mail status for %s: %s", mail_id, exc)
            return None
        finally:
            session.close()

    def is_available(self) -> bool:
        return len(self._providers) > 0

    def test_connection(self) -> Dict[str, Any]:
        results = {}
        for profile_id, provider in self._providers.items():
            result = provider.test_connection()
            results[profile_id] = {
                "success": result.success,
                "message": result.message,
                "provider": result.provider,
            }
        return {
            "available": self.is_available(),
            "providers": results,
        }

    def handle_unsubscribe(self, token: str, email_hash: str) -> bool:
        session = get_db_session()
        try:
            existing = session.query(MailUnsubscribe).filter_by(recipient_email_hash=email_hash).first()
            if existing:
                return True

            entry = MailUnsubscribe(
                id=str(uuid.uuid4()),
                recipient_email_hash=email_hash,
                reason="user_unsubscribed",
                created_at=_utc_now(),
            )
            session.add(entry)
            session.commit()
            logger.info("Unsubscribe recorded for hash=%s", email_hash)
            return True
        except Exception as exc:
            session.rollback()
            logger.error("Failed to record unsubscribe: %s", exc)
            return False
        finally:
            session.close()

    def is_unsubscribed(self, recipient_email: str) -> bool:
        email_hash = hashlib.sha256(recipient_email.encode("utf-8")).hexdigest()
        session = get_db_session()
        try:
            existing = session.query(MailUnsubscribe).filter_by(recipient_email_hash=email_hash).first()
            return existing is not None
        except Exception:
            return False
        finally:
            session.close()


mail_service = MailService()
