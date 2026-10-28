from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QLineEdit, QPushButton, QLabel
)

from core.auth_service import InvalidCredentials


class LoginDialog(QDialog):
    def __init__(self, auth):
        super().__init__()
        self._auth = auth
        self.setWindowTitle("Receipt Manager - Log in")

        self.username_box = QLineEdit()
        self.username_box.setPlaceholderText("Username")

        self.password_box = QLineEdit()
        self.password_box.setPlaceholderText("Password")
        self.password_box.setEchoMode(QLineEdit.EchoMode.Password)  # shows dots

        self.error_label = QLabel("")

        login_button = QPushButton("Log in")
        login_button.clicked.connect(self._try_login)
        self.password_box.returnPressed.connect(self._try_login)  # Enter key

        layout = QVBoxLayout(self)
        layout.addWidget(self.username_box)
        layout.addWidget(self.password_box)
        layout.addWidget(self.error_label)
        layout.addWidget(login_button)

    def _try_login(self):
        try:
            self._auth.login(self.username_box.text().strip(),
                             self.password_box.text())
            self.accept()          # closes the dialog as "success"
        except InvalidCredentials:
            self.error_label.setText("Wrong username or password.")
            self.password_box.clear()