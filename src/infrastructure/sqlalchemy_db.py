from sqlalchemy import create_engine
from sqlalchemy.orm import scoped_session, sessionmaker, declarative_base
from config.settings import get_config
import os

Base = declarative_base()
SessionLocal = None
engine = None

def _initialize():
    global engine, SessionLocal
    if engine is None:
        config = get_config()
        database_url = config.SQLALCHEMY_DATABASE_URI
        connect_args = {}
        if database_url.startswith('sqlite:'):
            connect_args = {'check_same_thread': False}
        engine = create_engine(database_url, future=True, echo=False, connect_args=connect_args)
        SessionLocal = scoped_session(sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True))

_initialize()

def init_db(app=None):
    _initialize()
    # Create all database tables for the current metadata.
    Base.metadata.create_all(engine)

    if app is not None:
        app.db_session = SessionLocal

    return engine


def get_db_session():
    _initialize()
    return SessionLocal()

