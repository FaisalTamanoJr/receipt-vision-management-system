"""
Login, logout and permission checks. Users and their logins live in
user_table/login_table and are read through the repositories, so this
file never touches SQLAlchemy.

The UI keeps one AuthService for the whole session and asks it
can_access(page) before showing a page. Code that changes data should
call require(page) so the check can't be skipped by the UI.
"""

from receipt_manager.auth.permissions import ROLE_PAGES, Page, RoleName
from receipt_manager.auth.security import check_password, hash_password, needs_rehash
from receipt_manager.core.models import Login, Role, User
from receipt_manager.data.repository import RoleRepository, UserRepository


class InvalidCredentials(Exception):
    pass


class PermissionDenied(Exception):
    pass


class UsernameTaken(Exception):
    pass


class AuthService:
    def __init__(
        self,
        users: UserRepository | None = None,
        roles: RoleRepository | None = None,
    ) -> None:
        self._users = users or UserRepository()
        self._roles = roles or RoleRepository()
        self.current_user: User | None = None  # nobody is logged in yet
        self.current_role: RoleName | None = None

    def login(self, username: str, password: str) -> User:
        user = self._users.get_by_username(username)
        if (
            user is None
            or not user.is_active
            or not check_password(user.login.password, password)
        ):
            raise InvalidCredentials()

        role = self._roles.get(user.role_id)
        if role is None or role.name not in {r.value for r in RoleName}:
            raise InvalidCredentials()  # a role this version of the app doesn't know

        # old scrypt hashes from the seed script get upgraded to argon2 here
        if needs_rehash(user.login.password):
            user.login.password = hash_password(password)
            user = self._users.update(user)

        self.current_user = user
        self.current_role = RoleName(role.name)
        return user

    def logout(self) -> None:
        self.current_user = None
        self.current_role = None

    def can_access(self, page: Page) -> bool:
        if self.current_role is None:
            return False
        return page in ROLE_PAGES[self.current_role]

    def require(self, page: Page) -> None:
        if not self.can_access(page):
            raise PermissionDenied(page.value)

    def _require_login(self) -> User:
        if self.current_user is None:
            raise PermissionDenied("not logged in")
        return self.current_user

    def change_password(self, current: str, new: str) -> None:
        user = self._require_login()
        if not check_password(user.login.password, current):
            raise InvalidCredentials()
        user.login.password = hash_password(new)
        self.current_user = self._users.update(user)

    def change_username(self, new: str) -> None:
        user = self._require_login()
        existing = self._users.get_by_username(new)
        if existing is not None and existing.id != user.id:
            raise UsernameTaken(new)
        user.login.username = new
        self.current_user = self._users.update(user)


def create_user(
    username: str,
    password: str,
    role: RoleName,
    *,
    fullname: str | None = None,
    email: str | None = None,
    users: UserRepository | None = None,
    roles: RoleRepository | None = None,
) -> User:
    """Adds a user with a login, creating the role row if it doesn't exist yet."""
    users = users or UserRepository()
    roles = roles or RoleRepository()

    if users.get_by_username(username) is not None:
        raise UsernameTaken(username)

    existing_role = roles.get_by_name(role.value)
    role_id = existing_role.id if existing_role else roles.add(Role(name=role.value)).id

    return users.add(
        User(
            role_id=role_id,
            fullname=fullname,
            email=email,
            # user_id is filled in by SQLAlchemy when the user is inserted
            login=Login(user_id=0, username=username, password=hash_password(password)),
        )
    )
