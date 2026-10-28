from sqlalchemy import select, func

from core.auth import Role, User
from core.security import hash_password
from core.models import UserRow


class UserRepository:
    def __init__(self, session_factory):
        self._session_factory = session_factory

    def get_by_username(self, username: str) -> User | None:
        with self._session_factory() as session:
            row = session.scalar(
                select(UserRow).where(UserRow.username == username)
            )
            if row is None:
                return None
            return User(
                id=row.id,
                username=row.username,
                password_hash=row.password_hash,
                role=Role(row.role),
                is_active=row.is_active,
            )

    def create_user(self, username: str, password: str, role: Role) -> None:
        with self._session_factory() as session:
            session.add(UserRow(
                username=username,
                password_hash=hash_password(password),
                role=role.value,
            ))
            session.commit()

    def count(self) -> int:
        with self._session_factory() as session:
            return session.scalar(select(func.count()).select_from(UserRow))