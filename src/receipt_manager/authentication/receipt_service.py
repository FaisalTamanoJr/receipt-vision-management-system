from core.auth import Page, Role
from core.auth_service import PermissionDenied


class StubReceiptService:
    """Temporary stand-in until the real OCR and database exist."""

    def __init__(self, auth):
        self._auth = auth
        self._next_id = 1
        self._uploaded_this_session = set()   # receipt ids this person uploaded

    def upload(self, image_path):
        self._auth.require(Page.UPLOAD)
        receipt_id = self._next_id
        self._next_id += 1
        self._uploaded_this_session.add(receipt_id)
        return receipt_id, "FAKE OCR TEXT\nStore: Example Mart\nTotal: 0.00"

    def update_text(self, receipt_id, new_text):
        self._auth.require(Page.UPLOAD)
        user = self._auth.current_user

        is_admin = user.role == Role.ADMIN
        is_own_upload = receipt_id in self._uploaded_this_session
        if not (is_admin or is_own_upload):
            raise PermissionDenied("You can only edit the receipt you just uploaded.")

        print(f"[stub] receipt {receipt_id} saved by {user.username}: {new_text!r}")