from PySide6.QtWidgets import QMainWindow, QTabWidget

from core.auth import Page
from upload_view import UploadView
from search_view import SearchView


class MainWindow(QMainWindow):
    def __init__(self, auth, receipts):
        super().__init__()
        self.setWindowTitle("Receipt Manager")
        tabs = QTabWidget()
        self.setCentralWidget(tabs)

        # (page, tab title, recipe that builds the page when called)
        all_pages = [
            (Page.UPLOAD, "Upload Receipt", lambda: UploadView(auth, receipts)),
            (Page.SEARCH, "Search", lambda: SearchView(auth)),
            # (Page.CHATBOT, "Assistant", lambda: ChatView(auth)),
            # (Page.BACKUP, "Backup", lambda: BackupView(auth)),
            # (Page.AUDIT_LOG, "Audit Log", lambda: AuditView(auth)),
            # (Page.USER_MANAGEMENT, "Users", lambda: UserManagementView(auth)),
        ]

        for page, title, build in all_pages:
            if auth.can_access(page):          # the keycard check
                tabs.addTab(build(), title)    # only built if allowed