from typing import Optional, List
from sqlalchemy.orm import Session
from src.infrastructure.pg_repositories.base import SqlAlchemyRepository
from src.infrastructure.models import Institution, Department, Course, CourseEnrollment, UserProfile

class PostgresInstitutionRepository(SqlAlchemyRepository[Institution]):
    def __init__(self, session: Optional[Session] = None):
        super().__init__(Institution, session)

    def get_by_code(self, code: str) -> Optional[Institution]:
        return self.get_by(code=code)

    def get_active_institutions(self) -> List[Institution]:
        return self.query(is_active=True)

class PostgresDepartmentRepository(SqlAlchemyRepository[Department]):
    def __init__(self, session: Optional[Session] = None):
        super().__init__(Department, session)

    def get_by_institution(self, institution_id: str) -> List[Department]:
        return self.query(institution_id=institution_id)

    def get_by_code(self, institution_id: str, code: str) -> Optional[Department]:
        return self.get_by(institution_id=institution_id, code=code)

class PostgresCourseRepository(SqlAlchemyRepository[Course]):
    def __init__(self, session: Optional[Session] = None):
        super().__init__(Course, session)

    def get_by_institution(self, institution_id: str) -> List[Course]:
        return self.query(institution_id=institution_id)

    def get_by_department(self, department_id: str) -> List[Course]:
        return self.query(department_id=department_id)

    def get_by_lecturer(self, lecturer_id: str) -> List[Course]:
        return self.query(lecturer_id=lecturer_id)

    def get_by_code(self, institution_id: str, code: str) -> Optional[Course]:
        return self.get_by(institution_id=institution_id, code=code)

    def get_by_institution_and_code(self, institution_id: str, code: str) -> Optional[Course]:
        return self.get_by(institution_id=institution_id, code=code)

class PostgresCourseEnrollmentRepository(SqlAlchemyRepository[CourseEnrollment]):
    def __init__(self, session: Optional[Session] = None):
        super().__init__(CourseEnrollment, session)

    def get_by_student(self, student_id: str) -> List[CourseEnrollment]:
        return self.query(student_id=student_id)

    def get_by_course(self, course_id: str) -> List[CourseEnrollment]:
        return self.query(course_id=course_id)

    def get_active_enrollments(self, course_id: str = None, student_id: str = None) -> List[CourseEnrollment]:
        filters = {'is_active': True}
        if course_id:
            filters['course_id'] = course_id
        if student_id:
            filters['student_id'] = student_id
        return self.query(**filters)

class PostgresUserProfileRepository(SqlAlchemyRepository[UserProfile]):
    def __init__(self, session: Optional[Session] = None):
        super().__init__(UserProfile, session)

    def get_by_user(self, user_id: str) -> Optional[UserProfile]:
        return self.get_by(user_id=user_id)

