"""
The application talks to the database through these repositories.
They only take and return the dataclasses from core/models.py,
data/mappers.py does the conversion to and from the orm rows.

Rules followed here:
- Every method opens its own session and commits when it's done,
  so callers never touch SQLAlchemy directly.
- Rows are converted to dataclasses before the session closes,
  since relationships load lazily.
- get/update return None and delete returns False when the id doesn't exist.
- Sorting only allows the columns listed in each _SORTABLE tuple,
  so a typo or user input can't reach order_by.

Helpful reference:
https://docs.sqlalchemy.org/en/20/orm/session_basics.html
https://docs.sqlalchemy.org/en/20/orm/queryguide/select.html
https://docs.sqlalchemy.org/en/20/orm/queryguide/relationships.html#selectin-eager-loading
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Generic, TypeVar

from sqlalchemy import Select, and_, extract, func, or_, select
from sqlalchemy.orm import Session, selectinload, sessionmaker

from receipt_manager.core.models import (
    InventoryItem,
    ProductType,
    Receipt,
    Role,
    Supplier,
    User,
)
from receipt_manager.data import mappers
from receipt_manager.data.engine import SessionLocal
from receipt_manager.data.orm_models import InventoryItem as InventoryItemRow
from receipt_manager.data.orm_models import Login as LoginRow
from receipt_manager.data.orm_models import ProductType as ProductTypeRow
from receipt_manager.data.orm_models import Receipt as ReceiptRow
from receipt_manager.data.orm_models import ReceiptItem as ReceiptItemRow
from receipt_manager.data.orm_models import Role as RoleRow
from receipt_manager.data.orm_models import Supplier as SupplierRow
from receipt_manager.data.orm_models import User as UserRow

DomainT = TypeVar("DomainT")
RowT = TypeVar("RowT")


# Base


# shared CRUD, subclasses only fill in the row class, the mappers and the sortable columns
class _Repository(Generic[DomainT, RowT]):
    _row_type: type[RowT]
    _to_domain: Callable[[RowT], DomainT]
    _to_row: Callable[[DomainT], RowT]
    _update_row: Callable[[RowT, DomainT], None]
    _SORTABLE: tuple[str, ...] = ("id",)

    # pass a different sessionmaker for testing (e.g. one bound to sqlite :memory:)
    def __init__(self, session_factory: sessionmaker[Session] = SessionLocal) -> None:
        self._session_factory = session_factory

    def _order_by(self, sort_by: str, descending: bool) -> list:
        if sort_by not in self._SORTABLE:
            raise ValueError(
                f"can't sort by {sort_by!r}, choose from {sorted(self._SORTABLE)}"
            )

        column = getattr(self._row_type, sort_by)
        # id is added last so rows with the same value keep a stable order
        id_column = self._row_type.id
        if descending:
            return [column.desc(), id_column.desc()]
        return [column.asc(), id_column.asc()]

    # override to eager load relationships that _to_domain always reads
    def _select(self) -> Select:
        return select(self._row_type)

    # INSERT, returns a copy with the new id filled in
    def add(self, obj: DomainT) -> DomainT:
        with self._session_factory.begin() as session:
            row = self._to_row(obj)
            session.add(row)
            session.flush()  # sends the INSERT so the id is generated
            return self._to_domain(row)

    def get(self, obj_id: int) -> DomainT | None:
        with self._session_factory() as session:
            row = session.scalars(
                self._select().where(self._row_type.id == obj_id)
            ).one_or_none()
            return self._to_domain(row) if row is not None else None

    def list_all(
        self,
        *,
        sort_by: str = "id",
        descending: bool = False,
        limit: int | None = None,
        offset: int = 0,
    ) -> list[DomainT]:
        stmt = (
            self._select()
            .order_by(*self._order_by(sort_by, descending))
            .limit(limit)
            .offset(offset)
        )
        with self._session_factory() as session:
            return [self._to_domain(row) for row in session.scalars(stmt)]

    def count(self) -> int:
        with self._session_factory() as session:
            return session.scalar(select(func.count()).select_from(self._row_type))

    # UPDATE, the dataclass must already have an id
    def update(self, obj: DomainT) -> DomainT | None:
        if obj.id is None:
            raise ValueError("can't update something that was never added, use add()")

        with self._session_factory.begin() as session:
            row = session.get(self._row_type, obj.id)
            if row is None:
                return None
            self._update_row(row, obj)
            session.flush()  # so new children get their ids before mapping back
            return self._to_domain(row)

    # owned children (receipt items, login, stock ledger) are deleted with it by the cascade
    def delete(self, obj_id: int) -> bool:
        with self._session_factory.begin() as session:
            row = session.get(self._row_type, obj_id)
            if row is None:
                return False
            session.delete(row)
            return True


# for tables with a unique name column (Role, ProductType, Supplier, InventoryItem)
class _NamedRepository(_Repository[DomainT, RowT]):
    _SORTABLE = ("id", "name")

    # exact match, ignoring case and surrounding spaces
    def get_by_name(self, name: str) -> DomainT | None:
        stmt = self._select().where(
            func.lower(self._row_type.name) == name.strip().lower()
        )
        with self._session_factory() as session:
            row = session.scalars(stmt).first()
            return self._to_domain(row) if row is not None else None

    # use before add() since the name column is unique
    def name_exists(self, name: str, *, exclude_id: int | None = None) -> bool:
        stmt = select(self._row_type.id).where(
            func.lower(self._row_type.name) == name.strip().lower()
        )
        if exclude_id is not None:
            stmt = stmt.where(self._row_type.id != exclude_id)
        with self._session_factory() as session:
            return session.scalar(stmt.limit(1)) is not None

    def search_by_name(self, text: str) -> list[DomainT]:
        stmt = (
            self._select()
            .where(self._row_type.name.icontains(text.strip(), autoescape=True))
            .order_by(self._row_type.name)
        )
        with self._session_factory() as session:
            return [self._to_domain(row) for row in session.scalars(stmt)]


# Role


class RoleRepository(_NamedRepository[Role, RoleRow]):
    _row_type = RoleRow
    _to_domain = staticmethod(mappers.role_to_domain)
    _to_row = staticmethod(mappers.role_to_row)
    _update_row = staticmethod(mappers.update_role_from_domain)


# User


class UserRepository(_Repository[User, UserRow]):
    _row_type = UserRow
    _to_domain = staticmethod(mappers.user_to_domain)
    _to_row = staticmethod(mappers.user_to_row)
    _update_row = staticmethod(mappers.update_user_from_domain)
    _SORTABLE = (
        "id",
        "fullname",
        "email",
        "date_created",
    )

    # login is always mapped, so load it with the user
    def _select(self) -> Select:
        return select(UserRow).options(selectinload(UserRow.login))

    # for the login screen, compare the password hash in the auth service, not here
    def get_by_username(self, username: str) -> User | None:
        stmt = self._select().join(UserRow.login).where(LoginRow.username == username)
        with self._session_factory() as session:
            row = session.scalars(stmt).one_or_none()
            return self._to_domain(row) if row is not None else None

    def list_by_role(self, role_id: int) -> list[User]:
        stmt = self._select().where(UserRow.role_id == role_id).order_by(UserRow.id)
        with self._session_factory() as session:
            return [self._to_domain(row) for row in session.scalars(stmt)]


# Receipt


# every field is optional, the ones left as None are ignored.
# All of the filled in fields must match (AND).
@dataclass(kw_only=True)
class ReceiptFilter:
    user_id: int | None = None

    # pick parts of the purchase date, e.g. year=2025, month=3 for all of March 2025
    year: int | None = None
    month: int | None = None
    day: int | None = None
    # inclusive range on purchase_date
    date_from: date | None = None
    date_to: date | None = None

    min_amount: Decimal | None = None
    max_amount: Decimal | None = None

    payment_method: str | None = None
    # receipts that have at least one item of this product type
    product_type_id: int | None = None
    # case-insensitive "contains" match on receipt_number or payer_name
    text: str | None = None


class ReceiptRepository(_Repository[Receipt, ReceiptRow]):
    _row_type = ReceiptRow
    _to_domain = staticmethod(mappers.receipt_to_domain)
    _to_row = staticmethod(mappers.receipt_to_row)
    _update_row = staticmethod(mappers.update_receipt_from_domain)
    _SORTABLE = (
        "id",
        "receipt_number",
        "purchase_date",
        "upload_date",
        "total_amount",
        "payer_name",
    )

    # items are always mapped, selectinload gets them for every receipt in one extra query
    # instead of one query per receipt
    def _select(self) -> Select:
        return select(ReceiptRow).options(selectinload(ReceiptRow.items))

    def _where(self, filters: ReceiptFilter) -> list:
        conditions = []

        if filters.user_id is not None:
            conditions.append(ReceiptRow.user_id == filters.user_id)

        if filters.year is not None:
            conditions.append(extract("year", ReceiptRow.purchase_date) == filters.year)
        if filters.month is not None:
            conditions.append(
                extract("month", ReceiptRow.purchase_date) == filters.month
            )
        if filters.day is not None:
            conditions.append(extract("day", ReceiptRow.purchase_date) == filters.day)
        if filters.date_from is not None:
            conditions.append(ReceiptRow.purchase_date >= filters.date_from)
        if filters.date_to is not None:
            conditions.append(ReceiptRow.purchase_date <= filters.date_to)

        if filters.min_amount is not None:
            conditions.append(ReceiptRow.total_amount >= filters.min_amount)
        if filters.max_amount is not None:
            conditions.append(ReceiptRow.total_amount <= filters.max_amount)

        if filters.payment_method:
            conditions.append(ReceiptRow.payment_method == filters.payment_method)

        if filters.product_type_id is not None:
            # any() becomes an EXISTS subquery, so a receipt with 3 matching items
            # still shows up once
            conditions.append(
                ReceiptRow.items.any(
                    ReceiptItemRow.inventory_item.has(
                        InventoryItemRow.product_type_id == filters.product_type_id
                    )
                )
            )

        if filters.text and filters.text.strip():
            text = filters.text.strip()
            conditions.append(
                or_(
                    ReceiptRow.receipt_number.icontains(text, autoescape=True),
                    ReceiptRow.payer_name.icontains(text, autoescape=True),
                )
            )

        return conditions

    # filtering + sorting + paging in one call, filters=None returns everything
    def find(
        self,
        filters: ReceiptFilter | None = None,
        *,
        sort_by: str = "purchase_date",
        descending: bool = True,
        limit: int | None = None,
        offset: int = 0,
    ) -> list[Receipt]:
        stmt = (
            self._select()
            .where(*self._where(filters or ReceiptFilter()))
            .order_by(*self._order_by(sort_by, descending))
            .limit(limit)
            .offset(offset)
        )
        with self._session_factory() as session:
            return [self._to_domain(row) for row in session.scalars(stmt)]

    # same filters as find(), for "showing 20 of 134" style paging
    def count_matching(self, filters: ReceiptFilter | None = None) -> int:
        stmt = (
            select(func.count())
            .select_from(ReceiptRow)
            .where(*self._where(filters or ReceiptFilter()))
        )
        with self._session_factory() as session:
            return session.scalar(stmt)

    # sum of total_amount for the same filters, Decimal(0) when nothing matches
    def total_amount(self, filters: ReceiptFilter | None = None) -> Decimal:
        stmt = select(func.sum(ReceiptRow.total_amount)).where(
            *self._where(filters or ReceiptFilter())
        )
        with self._session_factory() as session:
            total = session.scalar(stmt)
            return Decimal(total) if total is not None else Decimal(0)

    # A receipt counts as a duplicate when either:
    # - the receipt_number matches (ignoring case and surrounding spaces), or
    # - purchase_date, total_amount and payer_name all match, which catches
    #   the same receipt scanned twice where OCR misread the number.
    # The receipt itself is skipped when it already has an id, so this also works before update().
    # Nothing is blocked here, the review screen decides what to do with the matches.
    def find_duplicates(self, receipt: Receipt) -> list[Receipt]:
        same_details = and_(
            ReceiptRow.purchase_date == receipt.purchase_date,
            ReceiptRow.total_amount == receipt.total_amount,
            func.lower(func.trim(ReceiptRow.payer_name))
            == receipt.payer_name.strip().lower(),
        )

        # a blank number (OCR found nothing) would match every other blank one
        number = receipt.receipt_number.strip().lower()
        if number:
            same_number = func.lower(func.trim(ReceiptRow.receipt_number)) == number
            condition = or_(same_number, same_details)
        else:
            condition = same_details

        stmt = self._select().where(condition).order_by(ReceiptRow.id)
        if receipt.id is not None:
            stmt = stmt.where(ReceiptRow.id != receipt.id)

        with self._session_factory() as session:
            return [self._to_domain(row) for row in session.scalars(stmt)]

    def is_duplicate(self, receipt: Receipt) -> bool:
        return len(self.find_duplicates(receipt)) > 0


# Inventory


class ProductTypeRepository(_NamedRepository[ProductType, ProductTypeRow]):
    _row_type = ProductTypeRow
    _to_domain = staticmethod(mappers.product_type_to_domain)
    _to_row = staticmethod(mappers.product_type_to_row)
    _update_row = staticmethod(mappers.update_product_type_from_domain)


class SupplierRepository(_NamedRepository[Supplier, SupplierRow]):
    _row_type = SupplierRow
    _to_domain = staticmethod(mappers.supplier_to_domain)
    _to_row = staticmethod(mappers.supplier_to_row)
    _update_row = staticmethod(mappers.update_supplier_from_domain)


class InventoryItemRepository(_NamedRepository[InventoryItem, InventoryItemRow]):
    _row_type = InventoryItemRow
    _to_domain = staticmethod(mappers.inventory_item_to_domain)
    _to_row = staticmethod(mappers.inventory_item_to_row)
    _update_row = staticmethod(mappers.update_inventory_item_from_domain)
    _SORTABLE = (
        "id",
        "name",
        "average_daily_consumption",
    )

    # stock_ledger is always mapped, so load it with the item
    def _select(self) -> Select:
        return select(InventoryItemRow).options(
            selectinload(InventoryItemRow.stock_ledger)
        )

    def find(
        self,
        *,
        product_type_id: int | None = None,
        supplier_id: int | None = None,
        sort_by: str = "name",
        descending: bool = False,
    ) -> list[InventoryItem]:
        stmt = self._select()
        if product_type_id is not None:
            stmt = stmt.where(InventoryItemRow.product_type_id == product_type_id)
        if supplier_id is not None:
            stmt = stmt.where(InventoryItemRow.supplier_id == supplier_id)
        stmt = stmt.order_by(*self._order_by(sort_by, descending))

        with self._session_factory() as session:
            return [self._to_domain(row) for row in session.scalars(stmt)]
