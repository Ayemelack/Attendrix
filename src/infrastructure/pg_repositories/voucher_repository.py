from typing import Optional, List
from src.infrastructure.pg_repositories.base import SqlAlchemyRepository
from src.infrastructure.models import Voucher

class PostgresVoucherRepository(SqlAlchemyRepository[Voucher]):
    def __init__(self, session=None):
        super().__init__(Voucher, session)

    def get_by_code(self, code: str) -> Optional[Voucher]:
        return self.get_by(code=code)

    def add(self, entity: Voucher) -> Voucher:
        return self.create(entity)

    def mark_as_used(self, voucher_id: str, user_id: str) -> bool:
        from datetime import datetime
        voucher = self.get(voucher_id)
        if voucher and not voucher.is_used:
            voucher.is_used = True
            voucher.used_by = user_id
            voucher.used_at = datetime.utcnow()
            self.update(voucher)
            return True
        return False

    def mark_as_used_by_code(self, code: str, user_id: str) -> bool:
        from datetime import datetime
        voucher = self.get_by_code(code)
        if voucher and not voucher.is_used:
            voucher.is_used = True
            voucher.used_by = user_id
            voucher.used_at = datetime.utcnow()
            self.update(voucher)
            return True
        return False
