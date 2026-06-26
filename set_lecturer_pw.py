import sys, bcrypt, datetime
sys.path.insert(0, '.')
from src.infrastructure.repositories import user_repo
from src.infrastructure.firebase_service import FirebaseService

fb = FirebaseService()

lecturers = [
    ('lecturer.cs@attendrix.demo', 'lecturer123'),
    ('lecturer1@attendrix.demo', 'lecturer123'),
]

students = [
    ('student.cs1@attendrix.demo', 'student123'),
    ('student.cs2@attendrix.demo', 'student123'),
    ('student1@attendrix.demo', 'student123'),
]

all_users = lecturers + students

for email, pw in all_users:
    user = user_repo.get_by_email(email)
    if user:
        uid = user.get('id')
        pw_hash = bcrypt.hashpw(pw.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
        fb.update_document('users', uid, {'password_hash': pw_hash, 'updated_at': datetime.datetime.now(datetime.timezone.utc).isoformat()})
        print(f'OK  {email} -> {pw}')
    else:
        print(f'MISS  {email} not found')

print('\nDone')
