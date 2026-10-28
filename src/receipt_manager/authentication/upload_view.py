from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QFileDialog, QLabel, QPushButton, QSplitter, QTextEdit,
    QVBoxLayout, QWidget,
)

from core.auth import Page


class UploadView(QWidget):
    def __init__(self, auth, receipts):
        super().__init__()
        self._auth = auth
        self._receipts = receipts
        self._current_receipt_id = None          # nothing uploaded yet

        self.image_label = QLabel("The uploaded receipt image will show here")
        self.image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.text_box = QTextEdit()              # editable
        self.text_box.setPlaceholderText("Extracted text will show here")
        self.text_box.setEnabled(False)          # locked until something is uploaded

        splitter = QSplitter()
        splitter.addWidget(self.image_label)
        splitter.addWidget(self.text_box)

        upload_button = QPushButton("Upload receipt image")
        upload_button.clicked.connect(self._choose_file)

        self.save_button = QPushButton("Save changes")
        self.save_button.setEnabled(False)
        self.save_button.clicked.connect(self._save_text)

        done_button = QPushButton("Done / upload another")
        done_button.clicked.connect(self._clear)

        layout = QVBoxLayout(self)
        layout.addWidget(upload_button)
        layout.addWidget(splitter)
        layout.addWidget(self.save_button)
        layout.addWidget(done_button)

    def _choose_file(self):
        self._auth.require(Page.UPLOAD)
        path, _ = QFileDialog.getOpenFileName(
            self, "Choose a receipt image", "", "Images (*.png *.jpg *.jpeg)"
        )
        if not path:
            return                                # person cancelled

        receipt_id, extracted_text = self._receipts.upload(path)
        self._current_receipt_id = receipt_id

        self.image_label.setPixmap(
            QPixmap(path).scaled(400, 600, Qt.AspectRatioMode.KeepAspectRatio)
        )
        self.text_box.setPlainText(extracted_text)
        self.text_box.setEnabled(True)
        self.save_button.setEnabled(True)

    def _save_text(self):
        self._receipts.update_text(
            self._current_receipt_id, self.text_box.toPlainText()
        )

    def _clear(self):
        """Wipe the screen so the finished receipt is no longer visible."""
        self._current_receipt_id = None
        self.image_label.clear()
        self.image_label.setText("The uploaded receipt image will show here")
        self.text_box.clear()
        self.text_box.setEnabled(False)
        self.save_button.setEnabled(False)