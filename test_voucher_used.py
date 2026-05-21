import sys
sys.path.insert(0, '.')
from src.application.voucher_management_service import VoucherManagementService
from src.infrastructure.firebase_service import FirebaseService

fb = FirebaseService()
vs = VoucherManagementService(fb)
r = vs.list_vouchers('inst_001')
for v in r['vouchers']:
    if v.get('is_used'):
        print(f"{v['code']} - used_by: {v.get('used_by')} - email: {v.get('used_by_email')}")
