"""
This converts orm rows to dataclasses and vice-versa.

Helpful reference:
https://docs.sqlalchemy.org/en/20/orm/basic_relationships.html
https://docs.sqlalchemy.org/en/20/orm/cascades.html
"""

from __future__ import annotations

from receipt_manager.core.models import Receipt, ReceiptItem
from receipt_manager.data.orm_models import Receipt as ReceiptRow
from receipt_manager.data.orm_models import ReceiptItem as ReceiptItemRow

# Receipt Items


def item_to_domain(row: ReceiptItemRow) -> ReceiptItem:
    return ReceiptItem(
        id=row.id,
        receipt_id=row.receipt_id,
        inventory_item_id=row.inventory_item_id,
        quantity=row.quantity,
        unit_price=row.unit_price,
        total_price=row.total_price,
    )


def item_to_row(item: ReceiptItem, *, keep_id: bool = True) -> ReceiptRow:
    return ReceiptItemRow(
        id=item.id if keep_id else None,
        inventory_item_id=item.inventory_item_id,
        quantity=item.quantity,
        unit_price=item.unit_price,
        total_price=item.total_price,
    )


# Receipt

__RECEIPT_FIELDS__ = (
    "receipt_number",
    "original_image_path",
    "purchase_date",
    "upload_date",
    "total_amount",
    "payer_name",
    "payer_address",
    "payer_tin",
    "payment_method",
    "check_number",
    "bank_branch",
)


# Since row items load lazily, it is preferable to call this when session is still open.
def receipt_to_domain(row: ReceiptRow) -> Receipt:
    return Receipt(
        id=row.id,
        items=[item_to_domain(row_item) for row_item in row.items],
        **{getattr(row, name) for name in __RECEIPT_FIELDS__},
    )


# Used when making a new row (INSERT), otherwise use update_row_from_domain to update existing records
def receipt_to_row(receipt: Receipt) -> ReceiptRow:
    return ReceiptRow(
        id=receipt.id,
        items=[item_to_domain(receipt_item) for receipt_item in receipt.items],
        **{getattr(receipt, name) for name in __RECEIPT_FIELDS__},
    )


# copy the valeus from the dataclass into an existing row
def update_row_from_domain(row: ReceiptRow, receipt: Receipt) -> None:
    for name in __RECEIPT_FIELDS__:
        setattr(row, name, getattr(receipt, name))

    row.items.clear()
    row.items.extend(item_to_row(item, keep_id=False) for item in receipt.items)
