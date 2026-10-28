from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget


class SearchView(QWidget):
    """Placeholder admin-only page, to be replaced by the real search page."""

    def __init__(self, auth):
        super().__init__()
        user = auth.current_user

        label = QLabel(
            "Admin-only page (Search)\n\n"
            f"Logged in as: {user.username}  |  Role: {user.role.value}"
        )
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        layout = QVBoxLayout(self)
        layout.addWidget(label)