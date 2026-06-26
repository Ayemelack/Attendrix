import sys, os
sys.path.insert(0, '.')

# Load .env manually
from dotenv import load_dotenv
load_dotenv()
os.environ.setdefault('EMAIL_ENABLED', 'true')

from src.infrastructure.email_service import email_service
email_service._reload_config()

print(f"Provider: {email_service.provider}")
print(f"Available: {email_service.is_available}")
print(f"From: {email_service._config.get('from_email')}")
print(f"Resend key set: {bool(email_service._config.get('resend_api_key'))}")
print(f"Email enabled: {email_service._config.get('email_enabled')}")

# Send a test to the diag endpoint
result = email_service.send_email(
    to_email='diag@resend.dev',
    subject='Attendrix Email Test',
    html_body='<p>Test from Attendrix</p>',
)
print(f"\nSend result: {result}")
