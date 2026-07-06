from src.infrastructure.sqlalchemy_db import get_db_session
from src.infrastructure.pg_repositories.user_repository import PostgresUserRepository
from src.infrastructure.pg_repositories.voucher_repository import PostgresVoucherRepository
from src.infrastructure.pg_repositories.academic_repository import (
    PostgresInstitutionRepository, PostgresDepartmentRepository, 
    PostgresCourseRepository, PostgresCourseEnrollmentRepository, PostgresUserProfileRepository
)
from src.infrastructure.pg_repositories.telemetry_repository import (
    PostgresOfflineQueueRepository,
    PostgresNetworkPresenceRepository,
    PostgresActivityLogRepository,
    PostgresSecurityLogRepository,
    PostgresDeviceFingerprintRepository
)

# Generic property to lazily get session for global repos
class Repositories:
    @property
    def user(self):
        return PostgresUserRepository(get_db_session())
    
    @property
    def voucher(self):
        return PostgresVoucherRepository(get_db_session())
    
    @property
    def institution(self):
        return PostgresInstitutionRepository(get_db_session())
        
    @property
    def department(self):
        return PostgresDepartmentRepository(get_db_session())
        
    @property
    def course(self):
        return PostgresCourseRepository(get_db_session())

    @property
    def course_enrollment(self):
        return PostgresCourseEnrollmentRepository(get_db_session())
        
    @property
    def user_profile(self):
        return PostgresUserProfileRepository(get_db_session())

    @property
    def attendance_session(self):
        from src.infrastructure.pg_repositories.attendance_repository import PostgresAttendanceSessionRepository
        return PostgresAttendanceSessionRepository(get_db_session())

    @property
    def attendance_record(self):
        from src.infrastructure.pg_repositories.attendance_repository import PostgresAttendanceRecordRepository
        return PostgresAttendanceRecordRepository(get_db_session())

    @property
    def attendance_verification_log(self):
        from src.infrastructure.pg_repositories.attendance_repository import PostgresAttendanceVerificationLogRepository
        return PostgresAttendanceVerificationLogRepository(get_db_session())

    @property
    def offline_queue(self):
        return PostgresOfflineQueueRepository(get_db_session())

    @property
    def network_presence(self):
        return PostgresNetworkPresenceRepository(get_db_session())

    @property
    def activity_logs(self):
        return PostgresActivityLogRepository(get_db_session())

    @property
    def security_logs(self):
        return PostgresSecurityLogRepository(get_db_session())

    @property
    def device_fingerprint(self):
        return PostgresDeviceFingerprintRepository(get_db_session())

pg_repos = Repositories()
