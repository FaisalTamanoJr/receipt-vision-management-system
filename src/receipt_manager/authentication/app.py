import sys
from pathlib import Path

from platformdirs import user_data_dir
from PySide6.QtWidgets import QApplication, QDialog
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from core.auth_service import AuthService
from receipt_service import StubReceiptService
from core.models import Base
from core.user_repo import UserRepository
from login_dialog import LoginDialog
from main_window import MainWindow


def main():
    app = QApplication(sys.argv)

    data_dir = Path(user_data_dir("ReceiptManager", appauthor=False))
    data_dir.mkdir(parents=True, exist_ok=True)

    engine = create_engine(f"sqlite:///{data_dir / 'receipts.db'}")
    Base.metadata.create_all(engine)           # creates the users table
    session_factory = sessionmaker(engine)

    users = UserRepository(session_factory)
    auth = AuthService(users)
    receipts = StubReceiptService(auth) 

    login = LoginDialog(auth)
    if login.exec() != QDialog.DialogCode.Accepted:
        return                                  # window closed, quit

    window = MainWindow(auth, receipts)
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()