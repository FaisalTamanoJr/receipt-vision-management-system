"""
Which pages each role can open. The role names are the rows in
role_table (see scripts/seed.py), so a user's role is looked up by name.
"""

from enum import Enum


class RoleName(str, Enum):
    ADMIN = "Admin"
    STAFF = "Staff"


class Page(str, Enum):
    UPLOAD = "upload"  # upload page with the split screen
    SEARCH = "search"
    CHATBOT = "chatbot"
    BACKUP = "backup"
    AUDIT_LOG = "audit_log"
    USER_MANAGEMENT = "user_management"
    # Settings > Data Management, e.g. clearing all receipts
    DATA_MANAGEMENT = "data_management"


ROLE_PAGES = {
    RoleName.ADMIN: set(Page),  # every page
    RoleName.STAFF: {Page.UPLOAD},  # upload only
}
