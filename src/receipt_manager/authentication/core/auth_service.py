from core.auth import ROLE_PAGES, Page
from core.security import check_password


class InvalidCredentials(Exception):
    pass


class PermissionDenied(Exception):
    pass


class AuthService:
    def __init__(self, users):
        self._users = users
        self.current_user = None   # nobody is logged in yet

    def login(self, username: str, password: str):
        user = self._users.get_by_username(username)

        if (
            user is None
            or not user.is_active
            or not check_password(user.password_hash, password)
        ):
            raise InvalidCredentials()

        self.current_user = user
        return user

    def logout(self):
        self.current_user = None

    def can_access(self, page: Page) -> bool:
        if self.current_user is None:
            return False
        return page in ROLE_PAGES[self.current_user.role]

    def require(self, page: Page):
        if not self.can_access(page):
            raise PermissionDenied(page.value)