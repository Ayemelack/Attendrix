from typing import Optional, List
from src.infrastructure.pg_repositories.base import SqlAlchemyRepository
from src.infrastructure.models import User

class PostgresUserRepository(SqlAlchemyRepository[User]):
    def __init__(self, session=None):
        super().__init__(User, session)

    def get_by_email(self, email: str) -> Optional[User]:
        return self.get_by(email=email)
