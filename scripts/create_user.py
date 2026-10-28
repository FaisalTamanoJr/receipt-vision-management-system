"""
Adds an admin or staff account to your local database.
Runs the migrations first, so it works on a fresh database.

Usage:
    python scripts/create_user.py
"""

from getpass import getpass

from receipt_manager.auth.permissions import RoleName
from receipt_manager.auth.service import UsernameTaken, create_user
from receipt_manager.data.migrate import upgrade


def main() -> None:
    upgrade()

    username = input("Username: ").strip()
    password = getpass("Password: ")  # typing is hidden
    if getpass("Confirm password: ") != password:
        print("The passwords don't match.")
        return
    role_text = input("Role (admin/staff): ").strip().lower()
    fullname = input("Full name (optional): ").strip() or None

    role = RoleName.ADMIN if role_text == "admin" else RoleName.STAFF
    try:
        create_user(username, password, role, fullname=fullname)
    except UsernameTaken:
        print(f"{username} already exists.")
        return
    print(f"Created {role.value} account for {username}.")


if __name__ == "__main__":
    main()
