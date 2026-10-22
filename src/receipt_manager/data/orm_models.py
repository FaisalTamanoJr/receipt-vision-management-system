"""
These are the table definitions for the app.
However applications will interact with core/models.py.
data/mappers.py will connect this with models.py
to mirror any changes.

Helpful reference:
https://docs.sqlalchemy.org/en/20/tutorial/orm_related_objects.html#tutorial-orm-related-objects

For datatype objects see:
https://docs.sqlalchemy.org/en/21/core/types.html

For relationship patterns:
https://docs.sqlalchemy.org/en/21/orm/basic_relationships.html

column mapping:
https://docs.sqlalchemy.org/en/21/orm/declarative_tables.html
"""

from __future__ import annotations

from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column
from sqlalchemy.orm import relationship
from sqlalchemy.orm import DeclarativeBase

from sqlalchemy import ForeignKey
from sqlalchemy import Date
from sqlalchemy import DateTime
from sqlalchemy import Integer
from sqlalchemy import Numeric
from sqlalchemy import String
from sqlalchemy import TIMESTAMP

from datetime import date
from datetime import datetime
from decimal import Decimal


class Base(DeclarativeBase):
    type_annotation_map = {datetime: TIMESTAMP(timezone=True)}


# User
class Role(Base):
    __tablename__ = "role_table"

    id: Mapped[int] = mapped_column(primary_key=True)

    name: Mapped[str] = mapped_column(String(50), nullable=False, unique=True)

    users: Mapped[list[User] | None] = relationship(back_populates="role")


class Login(Base):
    __table__ = "login_table"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey="user_table.id")

    username: Mapped[str] = mapped_column(String(50), nullable=False, unique=True)
    password: Mapped[str] = mapped_column(String(255), nullable=False)

    user: Mapped[User] = relationship(back_populates="login")


class User(Base):
    __table__ = "user_table"

    id: Mapped[int] = mapped_column(primary_key=True)
    role_id: Mapped[int] = mapped_column(ForeignKey("role_table.id"))

    fullname: Mapped[str | None] = mapped_column(String(50))
    phone: Mapped[str | None] = mapped_column(String(15), unique=True)
    email: Mapped[str | None] = mapped_column(String(50), unique=True)
    birthday: Mapped[date | None] = mapped_column(Date)
    date_created: Mapped[date] = mapped_column(Date, default=date.today)

    role: Mapped[Role] = relationship(back_populates="users")
    login: Mapped[Login | None] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    receipts: Mapped[list[Receipt] | None] = relationship(back_populates="user")


# Receipts
class Receipt(Base):
    __table__ = "receipt_table"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("user_table.id"))

    original_image_path: Mapped[str] = mapped_column(String(255))
    purchase_date: Mapped[date] = mapped_column(Date, nullable=False)
    upload_date: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    total_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    payer_name: Mapped[str] = mapped_column(String(50), nullable=False)
    payer_tin: Mapped[str | None] = mapped_column(String(50), default="")
    payment_method: Mapped[str | None] = mapped_column(String(5), default="")
    check_number: Mapped[str | None] = mapped_column(String(50), default="")
    bank_branch: Mapped[str | None] = mapped_column(String(50), default="")

    user: Mapped[User] = relationship(back_populates="receipts")
    items: Mapped[list[ReceiptItem] | None] = relationship(
        back_populates="receipt", cascade="all, delete-orphan"
    )


class ReceiptItem(Base):
    __table__ = "receipt_item_table"

    id: Mapped[int] = mapped_column(primary_key=True)
    receipt_id: Mapped[int] = mapped_column(ForeignKey("receipt_table.id"))
    inventory_item_id: Mapped[int] = mapped_column(
        ForeignKey("inventory_item_table.id")
    )

    quantity: Mapped[int] = mapped_column(Integer)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    total_price: Mapped[Decimal] = mapped_column(Numeric(12, 2))

    receipt: Mapped[Receipt] = relationship(back_populates="items")
    inventory_item: Mapped[InventoryItem] = relationship(back_populates="receipt_items")


# Inventory
class ProductType(Base):
    __tablename__ = "product_type_table"

    id: Mapped[int] = mapped_column(primary_key=True)

    name: Mapped[str] = mapped_column(String(50), nullable=False, unique=True)

    products: Mapped[list[InventoryItem] | None] = relationship(
        back_populates="product_type"
    )


class InventoryItem(Base):
    __tablename__ = "inventory_item_table"

    id: Mapped[int] = mapped_column(primary_key=True)
    product_type_id: Mapped[int] = mapped_column(ForeignKey("product_type_table.id"))
    supplier_id: Mapped[int] = mapped_column(ForeignKey("supplier_table.id"))

    name: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    average_daily_consumption: Mapped[Decimal] = mapped_column(
        Decimal(12, 2), default=Decimal(0)
    )

    product_type: Mapped[ProductType] = relationship(back_populates="products")
    supplier: Mapped[Supplier] = relationship(back_populates="products")
    receipt_item: Mapped[list[ReceiptItem] | None] = relationship(
        back_populates="inventory_item"
    )
    stock_ledger: Mapped[StockLedger | None] = relationship(
        back_populates="inventory_item", cascade="all, delete-orphan"
    )


class StockLedger(Base):
    __tablename__ = "product_type_table"

    id: Mapped[int] = mapped_column(primary_key=True)
    inventory_item_id: Mapped[int] = mapped_column(
        ForeignKey("inventory_item_table.id")
    )

    current_quantity: Mapped[int] = mapped_column(Integer, default=0)
    last_updated: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)

    inventory_item: Mapped[InventoryItem] = relationship(back_populates="stock_ledger")


class Supplier(Base):
    __tablename__ = "supplier_table"

    id: Mapped[int] = mapped_column(primary_key=True)

    name: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    contact_info: Mapped[str] = mapped_column(String(255), default="", unique=True)

    products: Mapped[list[InventoryItem]] = relationship(back_populates="supplier")
