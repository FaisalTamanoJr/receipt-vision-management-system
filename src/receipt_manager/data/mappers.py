"""
This converts orm rows to dataclasses and vice-versa.

Rules followed here:
- *_to_domain: row -> dataclass. Relationships load lazily, so call these
  while the session is still open.
- *_to_row: dataclass -> new row (INSERT). Only "owned" children are copied
  (cascade="all, delete-orphan"), e.g. Receipt.items, User.login,
  InventoryItem.stock_ledger. Shared collections like Role.users or
  Supplier.products are linked through their foreign key ids instead,
  otherwise SQLAlchemy would insert duplicates.
- update_*_from_domain: copy dataclass values into an existing row (UPDATE).

Collections that are not owned (Role.users, User.receipts, Supplier.products,
...) are only mapped when include_children=True, so loading one Role doesn't
pull the whole database into memory.

Helpful reference:
https://docs.sqlalchemy.org/en/20/orm/basic_relationships.html
https://docs.sqlalchemy.org/en/20/orm/cascades.html
"""

from __future__ import annotations

from receipt_manager.core.models import (
    InventoryItem,
    Login,
    ProductType,
    Receipt,
    ReceiptItem,
    Role,
    StockLedger,
    Supplier,
    User,
)
from receipt_manager.data.orm_models import InventoryItem as InventoryItemRow
from receipt_manager.data.orm_models import Login as LoginRow
from receipt_manager.data.orm_models import ProductType as ProductTypeRow
from receipt_manager.data.orm_models import Receipt as ReceiptRow
from receipt_manager.data.orm_models import ReceiptItem as ReceiptItemRow
from receipt_manager.data.orm_models import Role as RoleRow
from receipt_manager.data.orm_models import StockLedger as StockLedgerRow
from receipt_manager.data.orm_models import Supplier as SupplierRow
from receipt_manager.data.orm_models import User as UserRow


def _copy_fields(source: object, names: tuple[str, ...]) -> dict:
    return {name: getattr(source, name) for name in names}


def _set_fields(target: object, source: object, names: tuple[str, ...]) -> None:
    for name in names:
        setattr(target, name, getattr(source, name))


# Role


_ROLE_FIELDS = ("name",)


def role_to_domain(row: RoleRow, *, include_children: bool = False) -> Role:
    return Role(
        id=row.id,
        users=[user_to_domain(user) for user in row.users] if include_children else [],
        **_copy_fields(row, _ROLE_FIELDS),
    )


def role_to_row(role: Role) -> RoleRow:
    return RoleRow(id=role.id, **_copy_fields(role, _ROLE_FIELDS))


def update_role_from_domain(row: RoleRow, role: Role) -> None:
    _set_fields(row, role, _ROLE_FIELDS)


# Login


_LOGIN_FIELDS = ("user_id", "username", "password")


def login_to_domain(row: LoginRow) -> Login:
    return Login(id=row.id, **_copy_fields(row, _LOGIN_FIELDS))


def login_to_row(login: Login, *, keep_id: bool = True) -> LoginRow:
    return LoginRow(
        id=login.id if keep_id else None,
        **_copy_fields(login, _LOGIN_FIELDS),
    )


def update_login_from_domain(row: LoginRow, login: Login) -> None:
    # user_id is left alone, the owning User row manages it
    row.username = login.username
    row.password = login.password


# User


_USER_FIELDS = (
    "role_id",
    "fullname",
    "phone",
    "email",
    "birthday",
    "date_created",
)


def user_to_domain(row: UserRow, *, include_children: bool = False) -> User:
    return User(
        id=row.id,
        login=login_to_domain(row.login) if row.login is not None else None,
        receipts=(
            [receipt_to_domain(receipt) for receipt in row.receipts]
            if include_children
            else []
        ),
        **_copy_fields(row, _USER_FIELDS),
    )


# User.receipts is not copied, receipts are inserted on their own with user_id set
def user_to_row(user: User) -> UserRow:
    return UserRow(
        id=user.id,
        login=login_to_row(user.login) if user.login is not None else None,
        **_copy_fields(user, _USER_FIELDS),
    )


def update_user_from_domain(row: UserRow, user: User) -> None:
    _set_fields(row, user, _USER_FIELDS)

    if user.login is None:
        row.login = None  # delete-orphan removes the old login
    elif row.login is None:
        row.login = login_to_row(user.login, keep_id=False)
    else:
        update_login_from_domain(row.login, user.login)


# Receipt Items


_ITEM_FIELDS = (
    "inventory_item_id",
    "quantity",
    "unit_price",
    "total_price",
)


def item_to_domain(row: ReceiptItemRow) -> ReceiptItem:
    return ReceiptItem(
        id=row.id,
        receipt_id=row.receipt_id,
        **_copy_fields(row, _ITEM_FIELDS),
    )


# receipt_id is filled in by SQLAlchemy once the row is added to Receipt.items
def item_to_row(item: ReceiptItem, *, keep_id: bool = True) -> ReceiptItemRow:
    return ReceiptItemRow(
        id=item.id if keep_id else None,
        **_copy_fields(item, _ITEM_FIELDS),
    )


def update_item_from_domain(row: ReceiptItemRow, item: ReceiptItem) -> None:
    _set_fields(row, item, _ITEM_FIELDS)


# Receipt


_RECEIPT_FIELDS = (
    "user_id",
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

# nullable in the table, but plain str (default "") in the dataclass
_RECEIPT_OPTIONAL_STR_FIELDS = frozenset(
    {"payer_address", "payer_tin", "payment_method", "check_number", "bank_branch"}
)


# Since row items load lazily, it is preferable to call this when session is still open.
def receipt_to_domain(row: ReceiptRow) -> Receipt:
    fields = _copy_fields(row, _RECEIPT_FIELDS)
    for name in _RECEIPT_OPTIONAL_STR_FIELDS:
        if fields[name] is None:
            fields[name] = ""

    return Receipt(
        id=row.id,
        items=[item_to_domain(row_item) for row_item in row.items],
        **fields,
    )


# Used when making a new row (INSERT), otherwise use update_receipt_from_domain to update existing records
def receipt_to_row(receipt: Receipt) -> ReceiptRow:
    return ReceiptRow(
        id=receipt.id,
        items=[item_to_row(receipt_item) for receipt_item in receipt.items],
        **_copy_fields(receipt, _RECEIPT_FIELDS),
    )


# copy the values from the dataclass into an existing row.
# Items are matched by id so unchanged items keep their ids:
# matching ids are updated, new items (id=None) are inserted, missing ones are deleted.
def update_receipt_from_domain(row: ReceiptRow, receipt: Receipt) -> None:
    _set_fields(row, receipt, _RECEIPT_FIELDS)

    existing = {row_item.id: row_item for row_item in row.items}
    new_items: list[ReceiptItemRow] = []
    for item in receipt.items:
        row_item = existing.get(item.id) if item.id is not None else None
        if row_item is None:
            row_item = item_to_row(item, keep_id=False)
        else:
            update_item_from_domain(row_item, item)
        new_items.append(row_item)

    # reassigning the list lets delete-orphan remove the dropped items
    row.items = new_items


# kept so existing callers don't break
update_row_from_domain = update_receipt_from_domain


# Stock Ledger


_STOCK_LEDGER_FIELDS = ("inventory_item_id", "current_quantity", "last_updated")


def stock_ledger_to_domain(row: StockLedgerRow) -> StockLedger:
    return StockLedger(id=row.id, **_copy_fields(row, _STOCK_LEDGER_FIELDS))


def stock_ledger_to_row(ledger: StockLedger, *, keep_id: bool = True) -> StockLedgerRow:
    return StockLedgerRow(
        id=ledger.id if keep_id else None,
        **_copy_fields(ledger, _STOCK_LEDGER_FIELDS),
    )


def update_stock_ledger_from_domain(row: StockLedgerRow, ledger: StockLedger) -> None:
    # inventory_item_id is left alone, the owning InventoryItem row manages it
    row.current_quantity = ledger.current_quantity
    row.last_updated = ledger.last_updated


# Inventory Item


_INVENTORY_ITEM_FIELDS = (
    "product_type_id",
    "supplier_id",
    "name",
    "average_daily_consumption",
)


def inventory_item_to_domain(
    row: InventoryItemRow, *, include_children: bool = False
) -> InventoryItem:
    return InventoryItem(
        id=row.id,
        stock_ledger=(
            stock_ledger_to_domain(row.stock_ledger)
            if row.stock_ledger is not None
            else None
        ),
        receipt_items=(
            [item_to_domain(row_item) for row_item in row.receipt_items]
            if include_children
            else []
        ),
        **_copy_fields(row, _INVENTORY_ITEM_FIELDS),
    )


# InventoryItem.receipt_items is not copied, those belong to receipts
def inventory_item_to_row(item: InventoryItem) -> InventoryItemRow:
    return InventoryItemRow(
        id=item.id,
        stock_ledger=(
            stock_ledger_to_row(item.stock_ledger)
            if item.stock_ledger is not None
            else None
        ),
        **_copy_fields(item, _INVENTORY_ITEM_FIELDS),
    )


def update_inventory_item_from_domain(
    row: InventoryItemRow, item: InventoryItem
) -> None:
    _set_fields(row, item, _INVENTORY_ITEM_FIELDS)

    if item.stock_ledger is None:
        row.stock_ledger = None  # delete-orphan removes the old ledger
    elif row.stock_ledger is None:
        row.stock_ledger = stock_ledger_to_row(item.stock_ledger, keep_id=False)
    else:
        update_stock_ledger_from_domain(row.stock_ledger, item.stock_ledger)


# Product Type


_PRODUCT_TYPE_FIELDS = ("name",)


def product_type_to_domain(
    row: ProductTypeRow, *, include_children: bool = False
) -> ProductType:
    return ProductType(
        id=row.id,
        products=(
            [inventory_item_to_domain(product) for product in row.products]
            if include_children
            else []
        ),
        **_copy_fields(row, _PRODUCT_TYPE_FIELDS),
    )


def product_type_to_row(product_type: ProductType) -> ProductTypeRow:
    return ProductTypeRow(
        id=product_type.id, **_copy_fields(product_type, _PRODUCT_TYPE_FIELDS)
    )


def update_product_type_from_domain(
    row: ProductTypeRow, product_type: ProductType
) -> None:
    _set_fields(row, product_type, _PRODUCT_TYPE_FIELDS)


# Supplier


_SUPPLIER_FIELDS = ("name", "contact_info")


def supplier_to_domain(row: SupplierRow, *, include_children: bool = False) -> Supplier:
    return Supplier(
        id=row.id,
        products=(
            [inventory_item_to_domain(product) for product in row.products]
            if include_children
            else []
        ),
        **_copy_fields(row, _SUPPLIER_FIELDS),
    )


def supplier_to_row(supplier: Supplier) -> SupplierRow:
    return SupplierRow(id=supplier.id, **_copy_fields(supplier, _SUPPLIER_FIELDS))


def update_supplier_from_domain(row: SupplierRow, supplier: Supplier) -> None:
    _set_fields(row, supplier, _SUPPLIER_FIELDS)
