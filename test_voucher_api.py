import requests, sys, json, time

base = 'http://localhost:5000'
session = requests.Session()

# Test 1: list vouchers with dev bypass
print("=== TEST 1: List vouchers ===")
r = session.get(f'{base}/api/voucher/list', params={'role': 'institutional_admin', 'institution_id': 'inst_001'})
print(f"Status: {r.status_code}")
if r.ok:
    data = r.json()
    print(f"Total: {data['total']}, Stats: {json.dumps(data['stats'])}")
else:
    print(f"Error: {r.text}")

# Test 2: generate batch
print("\n=== TEST 2: Generate vouchers ===")
payload = {'role': 'student', 'institution_id': 'inst_001', 'quantity': 3}
r = session.post(f'{base}/api/voucher/generate-batch', params={'role': 'institutional_admin'}, json=payload)
print(f"Status: {r.status_code}")
if r.ok:
    data = r.json()
    print(f"Generated: {len(data.get('vouchers', []))} vouchers")
    for v in data.get('vouchers', []):
        print(f"  {v['code']} - {v['role']}")
else:
    print(f"Error: {r.text}")

# Test 3: revoke a voucher
print("\n=== TEST 3: Revoke voucher ===")
r = session.get(f'{base}/api/voucher/list', params={'role': 'institutional_admin', 'institution_id': 'inst_001', 'per_page': 1})
if r.ok:
    data = r.json()
    vouchers = data.get('vouchers', [])
    if vouchers:
        vid = vouchers[0]['id']
        r2 = session.post(f'{base}/api/voucher/revoke/{vid}', params={'role': 'institutional_admin'})
        print(f"Revoke status: {r2.status_code}")
        if r2.ok:
            print(f"Result: {r2.json()}")
    else:
        print("No vouchers to revoke")

# Test 4: export CSV
print("\n=== TEST 4: Export CSV ===")
r = session.get(f'{base}/api/voucher/export/csv', params={'role': 'institutional_admin'})
print(f"Status: {r.status_code}")
if r.ok:
    print(f"CSV content (first 200 chars): {r.text[:200]}")
else:
    print(f"Error: {r.text}")

print("\n=== DONE ===")
