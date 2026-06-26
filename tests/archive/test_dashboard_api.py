import requests, json

token = open('token.txt').read().strip()
headers = {'Authorization': f'Bearer {token}'}
base = 'http://127.0.0.1:5000'

print('=== NETWORK STATUS ===')
r1 = requests.get(f'{base}/api/institutional/network-status', headers=headers)
d1 = r1.json()
print(f'Overall: {d1["overall_status"]}, Nodes: {len(d1["nodes"])}')
for n in d1['nodes']:
    print(f'  {n["name"]}: {n["status"]} ({n["latency_ms"]}ms)')

print()
print('=== SESSION HEALTH ===')
r2 = requests.get(f'{base}/api/institutional/session-health', headers=headers)
d2 = r2.json()
print(f'Active: {d2["active_sessions"]}, Total: {d2["total_sessions"]}')
for s in d2['sessions']:
    print(f'  {s["course"]}: {s["attendance_rate"]}% ({s["status"]})')

print()
print('=== CONSISTENCY CHECK ===')
r3a = requests.get(f'{base}/api/institutional/session-health', headers=headers)
r3b = requests.get(f'{base}/api/institutional/session-health', headers=headers)
d3a = r3a.json()
d3b = r3b.json()
print(f'Session health consistent: {d3a == d3b}')

print()
print('=== STUDENTS ===')
r4 = requests.get(f'{base}/api/institutional/students', headers=headers)
d4 = r4.json()
for s in d4['students']:
    print(f'  {s["name"]}: {s["attendance_pct"]}% (risk: {s["risk_level"]})')

print()
print('=== INFRASTRUCTURE ===')
r5 = requests.get(f'{base}/api/institutional/infrastructure', headers=headers)
d5 = r5.json()
print(f'UPS: {d5["ups"]["charge_pct"]}%')
for i in d5['isp']:
    print(f'  {i["name"]}: {i["status"]} ({i["latency_ms"]}ms)')

print()
print('=== COMPLIANCE ===')
r6 = requests.get(f'{base}/api/institutional/compliance', headers=headers)
d6 = r6.json()
print(f'Exam: {d6["exam_mode"]}, Type: {d6["exam_type"]}, GCE: {d6["gce_candidates"]}')

print()
print('=== PAYMENTS ===')
r7 = requests.get(f'{base}/api/institutional/payments', headers=headers)
d7 = r7.json()
print(f'Sales: {d7["voucher_sales_xaf"]} XAF, Txns: {len(d7["recent_txns"])}')

print()
print('=== P2P ===')
r8 = requests.get(f'{base}/api/institutional/p2p-sync', headers=headers)
d8 = r8.json()
print(f'Peers: {d8["total_neighbors"]}, Online: {d8["online_neighbors"]}')

print()
print('=== ACTIVITY FEED ===')
r9 = requests.get(f'{base}/api/institutional/activity-feed', headers=headers)
d9 = r9.json()
print(f'Activities: {len(d9["events"])}')
for e in d9['events'][:3]:
    print(f'  [{e["time"]}] {e["message"]}')

print()
print('=== ATTENDANCE TRENDS ===')
r10 = requests.get(f'{base}/api/institutional/attendance-trends', headers=headers)
d10 = r10.json()
print(f'Average: {d10["average"]}%, Days: {len(d10["daily_rates"])}')
print(f'Faculty Comparison: {len(d10["faculty_comparison"])} faculties')
for f in d10['faculty_comparison']:
    print(f'  {f["faculty"]}: {f["rate"]}%')
