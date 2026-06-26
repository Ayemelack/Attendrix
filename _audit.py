import json

with open('mock_database.json', 'r', encoding='utf-8') as f:
    db = json.load(f)

profiles = db.get('institution_profiles', [])
print('=== INSTITUTION PROFILES ===')
for p in profiles:
    print(f"  id={p.get('institution_id')}, name={p.get('name','?')}")

users = db.get('users', [])
courses = db.get('courses', [])
att_records = db.get('attendance_records', [])
sessions_data = db.get('attendance_sessions', [])

def safe(v):
    return v if v else ''

all_inst_ids = set()
for p in profiles:
    all_inst_ids.add(safe(p.get('institution_id')))
for u in users:
    all_inst_ids.add(safe(u.get('institution_id')))
for c in courses:
    all_inst_ids.add(safe(c.get('institution_id')))
for a in att_records:
    all_inst_ids.add(safe(a.get('institution_id')))

print(f'\nAll unique institution IDs across all collections: {sorted(all_inst_ids)}')

print('\n=== PER-INSTITUTION COUNTS ===')
for inst_id in sorted(all_inst_ids):
    if not inst_id:
        continue
    profile_name = next((p.get('name','?') for p in profiles if p.get('institution_id') == inst_id), 'N/A')
    admins = [u for u in users if u.get('institution_id') == inst_id and u.get('role') == 'institutional_admin']
    students_list = [u for u in users if u.get('institution_id') == inst_id and u.get('role') == 'student']
    inst_courses = [c for c in courses if c.get('institution_id') == inst_id]
    inst_att = [a for a in att_records if a.get('institution_id') == inst_id]
    print(f'Institution: {inst_id}  ({profile_name})')
    print(f'  admins:              {len(admins)}')
    print(f'  students:            {len(students_list)}')
    print(f'  courses:             {len(inst_courses)}')
    print(f'  attendance_records:  {len(inst_att)}')
    print()

# Count users without institution_id
null_inst = [u for u in users if not u.get('institution_id')]
print(f'Users with missing institution_id: {len(null_inst)}')
for u in null_inst:
    print(f'  {u.get("email")} role={u.get("role")}')

print()

# 4: Most recently created account
if users:
    last = users[-1]
    print('=== MOST RECENTLY CREATED ACCOUNT (last in array) ===')
    print(f'  email:          {last.get("email")}')
    print(f'  user_id:        {last.get("id")}')
    print(f'  role:           {last.get("role")}')
    print(f'  institution_id: {last.get("institution_id")}')
else:
    print('No users found')

print()

# 6: Check if dashboard_summary exists
summary = db.get('dashboard_summary', None)
if summary:
    print('=== DASHBOARD SUMMARY COLLECTION ===')
    for s in summary if isinstance(summary, list) else [summary]:
        print(json.dumps(s, indent=2)[:1000])
else:
    print('No dashboard_summary collection in mock DB.')

# Check institution_profiles for embedded stats
print('\n=== INSTITUTION PROFILES CONTENT ===')
for p in profiles:
    print(f"  {p.get('institution_id')}: {json.dumps(p, indent=4)[:300]}")
    print()

# Check if there's any "statistics" or "summary" collection
for key in db.keys():
    if any(word in key.lower() for word in ['summary', 'stat', 'cache', 'aggregate']):
        print(f'Found collection: {key}')
