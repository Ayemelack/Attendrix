from typing import TypeVar, Generic, Type, Optional, List, Dict, Any
from src.infrastructure.sqlalchemy_db import get_db_session
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError

T = TypeVar('T')

class SqlAlchemyRepository(Generic[T]):
    def __init__(self, model_class: Type[T], session: Optional[Session] = None):
        self.model_class = model_class
        # Prefer provided session (for transactions), fallback to scoped session
        self._session = session

    @property
    def session(self) -> Session:
        return self._session if self._session else get_db_session()

    def get(self, id: Any) -> Optional[T]:
        return self.session.query(self.model_class).get(id)

    def get_by(self, **kwargs) -> Optional[T]:
        return self.session.query(self.model_class).filter_by(**kwargs).first()

    def query(self, **kwargs) -> List[T]:
        return self.session.query(self.model_class).filter_by(**kwargs).all()

    def list_all(self, limit: int = 1000) -> List[T]:
        return self.session.query(self.model_class).limit(limit).all()

    def create(self, entity: T) -> T:
        try:
            self.session.add(entity)
            self.session.commit()
            self.session.refresh(entity)
            return entity
        except SQLAlchemyError as e:
            self.session.rollback()
            raise e

    def update(self, entity: T) -> T:
        try:
            self.session.commit()
            self.session.refresh(entity)
            return entity
        except SQLAlchemyError as e:
            self.session.rollback()
            raise e

    def delete(self, entity: T) -> None:
        try:
            self.session.delete(entity)
            self.session.commit()
        except SQLAlchemyError as e:
            self.session.rollback()
            raise e
