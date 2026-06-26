"""Tests for Attendrix Mail subsystem (mail_models, mail_providers, mail_service)."""

import os
import sys
import uuid
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

os.environ['DATABASE_URL'] = 'sqlite:///test_attendrix_mail.db'
os.environ['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///test_attendrix_mail.db'
os.environ['USE_MOCK_FIREBASE'] = 'true'
os.environ['MAIL_UNSUBSCRIBE_SALT'] = 'test-salt'


from src.infrastructure.sqlalchemy_db import init_db, Base, get_db_session
from src.infrastructure.mail_models import (
    MailQueue, MailTemplate, MailAuditLog, MailSmtpProfile, MailUnsubscribe,
    MailStatus, MailEventType, MailTemplateCategory,
)
from src.infrastructure.mail_providers import (
    SMTPMailProvider, ResendMailProvider,
    EmailEnvelope, SendResult,
)
from src.infrastructure.mail_service import (
    MailService, _load_template_file, _render_template,
    _build_unsubscribe_token, _build_unsubscribe_url,
    CATEGORY_TEMPLATE_MAP, TEMPLATES_DIR,
)


_engine = init_db()
Base.metadata.create_all(_engine)


class TestMailModels(unittest.TestCase):
    def setUp(self):
        self.session = get_db_session()
        for tbl in [MailUnsubscribe, MailAuditLog, MailQueue, MailTemplate, MailSmtpProfile]:
            self.session.query(tbl).delete()
        self.session.commit()

    def tearDown(self):
        self.session.close()

    def test_create_mail_queue_entry(self):
        mail = MailQueue(
            id=str(uuid.uuid4()),
            recipient_email='test@example.com',
            recipient_name='Test User',
            subject='Test Subject',
            body_html='<p>Hello</p>',
            status=MailStatus.PENDING.value,
            tracking_id=str(uuid.uuid4()),
        )
        self.session.add(mail)
        self.session.commit()

        saved = self.session.query(MailQueue).filter_by(recipient_email='test@example.com').first()
        self.assertIsNotNone(saved)
        self.assertEqual(saved.subject, 'Test Subject')
        self.assertEqual(saved.status, 'pending')

    def test_mail_status_enum(self):
        self.assertEqual(MailStatus.PENDING.value, 'pending')
        self.assertEqual(MailStatus.SENT.value, 'sent')
        self.assertEqual(MailStatus.FAILED.value, 'failed')
        self.assertEqual(MailStatus.RETRYING.value, 'retrying')
        self.assertEqual(MailStatus.CANCELLED.value, 'cancelled')

    def test_mail_template_creation(self):
        tpl = MailTemplate(
            id=str(uuid.uuid4()),
            template_name='test_template',
            category=MailTemplateCategory.VOUCHER_DELIVERY.value,
            subject_template='Hello $name',
            body_template='<p>Hi $name</p>',
        )
        self.session.add(tpl)
        self.session.commit()

        saved = self.session.query(MailTemplate).filter_by(template_name='test_template').first()
        self.assertIsNotNone(saved)
        self.assertEqual(saved.category, 'voucher_delivery')

    def test_mail_audit_log(self):
        mail_id = str(uuid.uuid4())
        log = MailAuditLog(
            id=str(uuid.uuid4()),
            mail_id=mail_id,
            event_type=MailEventType.QUEUED.value,
            details={'info': 'test'},
        )
        self.session.add(log)
        self.session.commit()

        saved = self.session.query(MailAuditLog).filter_by(mail_id=mail_id).first()
        self.assertIsNotNone(saved)
        self.assertEqual(saved.event_type, 'queued')

    def test_mail_smtp_profile(self):
        profile = MailSmtpProfile(
            id=str(uuid.uuid4()),
            name='test_smtp',
            host='smtp.example.com',
            port=587,
            from_email='noreply@example.com',
            is_primary=True,
        )
        self.session.add(profile)
        self.session.commit()

        saved = self.session.query(MailSmtpProfile).filter_by(name='test_smtp').first()
        self.assertIsNotNone(saved)
        self.assertTrue(saved.is_primary)

    def test_mail_unsubscribe(self):
        entry = MailUnsubscribe(
            id=str(uuid.uuid4()),
            recipient_email_hash='abc123hash',
        )
        self.session.add(entry)
        self.session.commit()

        saved = self.session.query(MailUnsubscribe).filter_by(
            recipient_email_hash='abc123hash'
        ).first()
        self.assertIsNotNone(saved)


class TestMailProviders(unittest.TestCase):
    def test_smtp_provider_init(self):
        p = SMTPMailProvider(
            host='smtp.example.com', port=587, username='u',
            password='p', from_email='noreply@example.com',
        )
        self.assertEqual(p.host, 'smtp.example.com')

    def test_resend_provider_init(self):
        p = ResendMailProvider(api_key='re_test', from_email='noreply@example.com')
        self.assertEqual(p.api_key, 're_test')

    def test_smtp_connection_fails_gracefully(self):
        p = SMTPMailProvider(host='192.0.2.1', port=25, timeout=2)
        result = p.test_connection()
        self.assertFalse(result.success)

    def test_envelope_dataclass(self):
        e = EmailEnvelope(
            recipient_email='test@example.com', recipient_name='T',
            subject='S', html_body='<p>B</p>',
        )
        self.assertEqual(e.recipient_email, 'test@example.com')

    def test_resend_test_no_key(self):
        p = ResendMailProvider(api_key='')
        self.assertFalse(p.test_connection().success)

    def test_resend_test_with_key(self):
        p = ResendMailProvider(api_key='re_valid')
        self.assertTrue(p.test_connection().success)


class TestMailService(unittest.TestCase):
    def setUp(self):
        self.service = MailService()
        self.service._initialized = False
        self.service._providers = {}
        session = get_db_session()
        for tbl in [MailUnsubscribe, MailAuditLog, MailQueue, MailTemplate, MailSmtpProfile]:
            session.query(tbl).delete()
        session.commit()
        session.close()

    def test_template_loading(self):
        for category, filename in CATEGORY_TEMPLATE_MAP.items():
            content = _load_template_file(filename)
            self.assertIsNotNone(content)
            self.assertTrue(len(content) > 0)

    def test_base_layout_exists(self):
        self.assertTrue(os.path.exists(os.path.join(TEMPLATES_DIR, 'base_layout.html')))

    def test_template_rendering(self):
        result = _render_template('Hello $name, code=$code', {'name': 'John', 'code': 'ABC'})
        self.assertEqual(result, 'Hello John, code=ABC')

    def test_unsubscribe_token(self):
        t1 = _build_unsubscribe_token('test@example.com')
        t2 = _build_unsubscribe_token('test@example.com')
        self.assertEqual(t1, t2)
        self.assertEqual(len(t1), 64)

    def test_unsubscribe_url(self):
        url = _build_unsubscribe_url('test@example.com', app_url='http://localhost:5000')
        self.assertIn('http://localhost:5000', url)
        self.assertIn('token=', url)

    def test_queue_email_no_template(self):
        result = self.service.queue_email(
            template_type='nonexistent', recipient_email='a@b.com',
            variables={'name': 'Test'},
        )
        self.assertIsNone(result)

    def test_seed_templates(self):
        self.service._seed_default_templates()
        session = get_db_session()
        count = session.query(MailTemplate).count()
        session.close()
        self.assertEqual(count, len(CATEGORY_TEMPLATE_MAP))

    def test_queue_stats_empty(self):
        self.assertEqual(self.service.get_queue_stats().get('total'), 0)

    def test_queue_email_and_stats(self):
        self.service._seed_default_templates()
        mail_id = self.service.queue_email(
            template_type='voucher_delivery',
            recipient_email='student@example.com',
            variables={'recipient_name': 'John', 'role_name': 'Student',
                       'voucher_code': 'TEST1234', 'expires_at': '2026-12-31'},
            recipient_name='John',
        )
        self.assertIsNotNone(mail_id)
        stats = self.service.get_queue_stats()
        self.assertEqual(stats['total'], 1)
        self.assertEqual(stats['pending'], 1)

    def test_cancel_email(self):
        self.service._seed_default_templates()
        mail_id = self.service.queue_email(
            template_type='voucher_delivery', recipient_email='t@t.com',
            variables={'recipient_name': 'T', 'role_name': 'S', 'voucher_code': 'X', 'expires_at': 'N/A'},
        )
        self.assertTrue(self.service.cancel_email(mail_id))
        session = get_db_session()
        mail = session.query(MailQueue).filter_by(id=mail_id).first()
        session.close()
        self.assertEqual(mail.status, 'cancelled')

    def test_get_templates(self):
        self.service._seed_default_templates()
        templates = self.service.get_templates()
        names = [t['template_name'] for t in templates]
        self.assertIn('voucher_delivery', names)
        self.assertIn('demo_confirmation', names)
        self.assertIn('password_reset', names)

    def test_retry_failed_emails(self):
        self.service._seed_default_templates()
        mail_id = self.service.queue_email(
            template_type='voucher_delivery', recipient_email='t@t.com',
            variables={'recipient_name': 'T', 'role_name': 'S', 'voucher_code': 'X', 'expires_at': 'N/A'},
        )
        session = get_db_session()
        mail = session.query(MailQueue).filter_by(id=mail_id).first()
        mail.status = 'failed'
        mail.retry_count = 3
        session.commit()
        session.close()

        self.assertEqual(self.service.retry_failed_emails(), 1)
        session = get_db_session()
        mail = session.query(MailQueue).filter_by(id=mail_id).first()
        session.close()
        self.assertEqual(mail.status, 'retrying')

    def test_audit_log_on_queue(self):
        self.service._seed_default_templates()
        mail_id = self.service.queue_email(
            template_type='voucher_delivery', recipient_email='t@t.com',
            variables={'recipient_name': 'T', 'role_name': 'S', 'voucher_code': 'X', 'expires_at': 'N/A'},
        )
        logs = self.service.get_audit_logs()
        mail_logs = [l for l in logs if l['mail_id'] == mail_id]
        self.assertTrue(len(mail_logs) >= 1)
        self.assertEqual(mail_logs[0]['event_type'], 'queued')

    def test_is_available_no_provider(self):
        self.assertFalse(self.service.is_available())

    def test_test_connection_no_provider(self):
        self.assertFalse(self.service.test_connection()['available'])

    def test_unsubscribe_flow(self):
        self.assertTrue(self.service.handle_unsubscribe('valid_token', 'hash123'))
        session = get_db_session()
        entry = session.query(MailUnsubscribe).filter_by(recipient_email_hash='hash123').first()
        session.close()
        self.assertIsNotNone(entry)

    def test_multiple_queue(self):
        self.service._seed_default_templates()
        for i in range(5):
            self.service.queue_email(
                template_type='voucher_delivery', recipient_email=f's{i}@e.com',
                variables={'recipient_name': f'S{i}', 'role_name': 'S',
                           'voucher_code': f'C{i}', 'expires_at': 'N/A'},
            )
        self.assertEqual(self.service.get_queue_stats()['total'], 5)

    def test_log_mail_event(self):
        self.service._seed_default_templates()
        mail_id = self.service.queue_email(
            template_type='voucher_delivery', recipient_email='t@t.com',
            variables={'recipient_name': 'T', 'role_name': 'S', 'voucher_code': 'X', 'expires_at': 'N/A'},
        )
        self.assertTrue(self.service.log_mail_event(mail_id, 'delivered', {'provider': 'smtp'}))

    def test_get_queue_emails(self):
        self.service._seed_default_templates()
        self.service.queue_email(
            template_type='voucher_delivery', recipient_email='a@a.com',
            variables={'recipient_name': 'A', 'role_name': 'S', 'voucher_code': 'X', 'expires_at': 'N/A'},
        )
        self.service.queue_email(
            template_type='demo_confirmation', recipient_email='b@b.com',
            variables={'recipient_name': 'B', 'institution': 'U', 'demo_date': 'D',
                       'demo_time': 'T', 'timezone': 'Z', 'portal_url': 'http://x'},
        )
        emails = self.service.get_queue_emails()
        self.assertEqual(len(emails), 2)

    def test_get_queue_emails_filtered(self):
        self.service._seed_default_templates()
        self.service.queue_email(
            template_type='voucher_delivery', recipient_email='a@a.com',
            variables={'recipient_name': 'A', 'role_name': 'S', 'voucher_code': 'X', 'expires_at': 'N/A'},
        )
        emails = self.service.get_queue_emails(status_filter='pending')
        self.assertTrue(len(emails) >= 1)
        self.assertTrue(all(e['status'] == 'pending' for e in emails))


if __name__ == '__main__':
    unittest.main()
