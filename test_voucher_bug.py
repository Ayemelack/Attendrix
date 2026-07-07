import sys
from app import app
from src.infrastructure.pg_repositories import pg_repos
from datetime import datetime, timedelta

with app.app_context():
    code = "ADMIN123"
    voucher = pg_repos.voucher.get_by_code(code)
    if voucher:
        print("Voucher found.")
        print(f"Expires: {voucher.expires_at} ({type(voucher.expires_at)})")
        print(f"Created: {voucher.created_at} ({type(voucher.created_at)})")
        try:
            expiry_date = voucher.expires_at if voucher.expires_at else (voucher.created_at + timedelta(days=90) if voucher.created_at else datetime.utcnow())
            if datetime.utcnow() > expiry_date:
                print("Expired")
            else:
                print("Valid")
        except Exception as e:
            import traceback
            traceback.print_exc()
    else:
        print("Voucher not found.")
