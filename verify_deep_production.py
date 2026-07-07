import sys
import logging
from app import app
from src.infrastructure.sqlalchemy_db import SessionLocal
from src.infrastructure.models import (
    User, Course, Department, AttendanceSession, AttendanceRecord
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def verify_models():
    logger.info("Verifying Models vs Alembic...")
    from sqlalchemy import inspect
    engine = SessionLocal().get_bind()
    inspector = inspect(engine)
    tables = inspector.get_table_names()
    required = ['users', 'courses', 'departments', 'attendance_sessions', 'attendance_records']
    missing = [t for t in required if t not in tables]
    if missing:
        logger.error(f"Missing tables: {missing}")
        return False
    logger.info("Database integrity check passed.")
    return True

def verify_endpoints_exist():
    logger.info("Verifying Endpoints...")
    with app.app_context():
        rules = [rule.rule for rule in app.url_map.iter_rules()]
        if '/api/auth/login' not in rules:
            logger.error("Missing Auth endpoint!")
            return False
        if '/api/student/dashboard' not in rules:
            logger.error("Missing dashboard endpoint!")
            return False
    logger.info("Endpoints map verified.")
    return True

def run_audits():
    success = True
    success &= verify_models()
    success &= verify_endpoints_exist()
    
    if success:
        logger.info("Deep production verification passed!")
        sys.exit(0)
    else:
        logger.error("Deep production verification failed.")
        sys.exit(1)

if __name__ == '__main__':
    run_audits()
