from pathlib import Path
from getpass import getpass

from platformdirs import user_data_dir
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from core.auth import Role
from core.models import Base
from core.user_repo import UserRepository

data_dir = Path(user_data_dir("ReceiptManager", appauthor=False))
data_dir.mkdir(parents=True, exist_ok=True)
engine = create_engine(f"sqlite:///{data_dir / 'receipts.db'}")
Base.metadata.create_all(engine)

repo = UserRepository(sessionmaker(engine))
username = input("Username: ")
password = getpass("Password: ")   # typing is hidden
role_text = input("Role (admin/user): ").strip().lower()

role = Role.ADMIN if role_text == "admin" else Role.USER
repo.create_user(username, password, role)
print(f"Created {role.value} account for {username}.")