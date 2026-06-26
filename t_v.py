import sys
sys.path.insert(0, '.')
from src.application.voucher_management_service import VoucherManagementService
from src.infrastructure.firebase_service import FirebaseService
from src.domain.entities import UserRole

fb = FirebaseService()
vs = VoucherManagementService(fb)

v = vs.generate_voucher_batch(UserRole.LECTURER, 'inst_001', 2, generated_by='admin@test.com')
print('Generated:', len(v))
for x in v:
    print(f'  {x["code"]} - gen_by: {x["generated_by"]}')

r = vs.list_vouchers('inst_001', search='LECT456')
print('Search results:', r['total'])

r2 = vs.list_vouchers('inst_001', status_filter='active', role_filter='lecturer')
print('Filtered:', r2['total'], [x['code'] for x in r2['vouchers']])

if r2['vouchers']:
    ok = vs.revoke_voucher(r2['vouchers'][0]['id'])
    print('Revoke:', ok)

r3 = vs.list_vouchers('inst_001')
print('Stats:', r3['stats'])
print('ALL OK')
