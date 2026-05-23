from models import User
from repositories.base_repository import BaseRepository
from utils.db import db


class UserRepository(BaseRepository):
    def get_by_id(self, user_id: int) -> User | None:
        return db.session.get(User, user_id)

    def find_by_email(self, email: str) -> User | None:
        return db.session.execute(
            db.select(User).where(User.email == email.lower().strip())
        ).scalar_one_or_none()

    def find_superadmin_by_email(self, email: str) -> User | None:
        return db.session.execute(
            db.select(User).where(
                User.email == email.lower().strip(),
                User.is_superadmin.is_(True),
            )
        ).scalar_one_or_none()
