from dataclasses import dataclass
from enum import Enum


class Role(str, Enum):
    ADMIN = "admin"
    USER = "user"


class Page(str, Enum):
    UPLOAD = "upload"            # upload page with the split screen
    SEARCH = "search"
    CHATBOT = "chatbot"
    BACKUP = "backup"
    AUDIT_LOG = "audit_log"
    USER_MANAGEMENT = "user_management"


ROLE_PAGES = {
    Role.ADMIN: set(Page),       # every page
    Role.USER: {Page.UPLOAD},    # upload only
}


@dataclass
class User:
    id: int
    username: str
    password_hash: str
    role: Role
    is_active: bool