"""
Fills the database with sample data for development.
Runs the migrations first, so it works on a fresh database.

Safe to run more than once, anything that already exists
(matched by name, username or receipt number) is skipped.

Usage:
    python scripts/seed.py

Default logins (change these before handing the app to anyone):
    admin / admin123
    staff / staff123
"""

import hashlib
import os
from datetime import date
from decimal import Decimal

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
from receipt_manager.data.migrate import upgrade
from receipt_manager.data.repository import (
    InventoryItemRepository,
    ProductTypeRepository,
    ReceiptRepository,
    RoleRepository,
    SupplierRepository,
    UserRepository,
)


# placeholder until the auth service exists, it has to verify with the same format:
# "scrypt$<salt hex>$<hash hex>"
def hash_password(password: str) -> str:
    salt = os.urandom(16)
    digest = hashlib.scrypt(password.encode(), salt=salt, n=2**14, r=8, p=1)
    return f"scrypt${salt.hex()}${digest.hex()}"


# returns the existing row's id or adds a new one
def named(repo, obj) -> int:
    existing = repo.get_by_name(obj.name)
    if existing is not None:
        return existing.id
    return repo.add(obj).id


def seed_users(roles: RoleRepository, users: UserRepository) -> int:
    admin_role = named(roles, Role(name="Admin"))
    staff_role = named(roles, Role(name="Staff"))

    accounts = [
        (admin_role, "admin", "admin123", "System Administrator", "admin@example.com"),
        (staff_role, "staff", "staff123", "Juan Dela Cruz", "staff@example.com"),
    ]
    admin_id = None
    for role_id, username, password, fullname, email in accounts:
        user = users.get_by_username(username)
        if user is None:
            user = users.add(
                User(
                    role_id=role_id,
                    fullname=fullname,
                    email=email,
                    # user_id is filled in by SQLAlchemy when the user is inserted
                    login=Login(
                        user_id=0, username=username, password=hash_password(password)
                    ),
                )
            )
        if username == "admin":
            admin_id = user.id
    return admin_id


def seed_inventory(
    product_types: ProductTypeRepository,
    suppliers: SupplierRepository,
    items: InventoryItemRepository,
) -> dict[str, int]:
    implants = named(product_types, ProductType(name="Implants"))
    instruments = named(product_types, ProductType(name="Surgical Instruments"))
    consumables = named(product_types, ProductType(name="Consumables"))

    medtech = named(
        suppliers, Supplier(name="MedTech Supplies Inc.", contact_info="0917 123 4567")
    )
    spinecare = named(
        suppliers,
        Supplier(name="SpineCare Distributors", contact_info="(02) 8123 4567"),
    )

    # name, product type, supplier, stock on hand, average daily consumption
    catalog = [
        ("Pedicle Screw 6.5mm", implants, spinecare, 120, "3.50"),
        ("Titanium Rod 5.5mm", implants, spinecare, 40, "1.25"),
        ("Bone Graft Substitute 5cc", implants, medtech, 25, "0.80"),
        ("Kerrison Rongeur", instruments, medtech, 6, "0"),
        ("Surgical Gloves (box)", consumables, medtech, 50, "2.00"),
        ("Sterile Gauze Pack", consumables, medtech, 200, "8.00"),
    ]
    ids = {}
    for name, type_id, supplier_id, quantity, daily in catalog:
        ids[name] = named(
            items,
            InventoryItem(
                product_type_id=type_id,
                supplier_id=supplier_id,
                name=name,
                average_daily_consumption=Decimal(daily),
                stock_ledger=StockLedger(
                    inventory_item_id=0, current_quantity=quantity
                ),
            ),
        )
    return ids


def receipt_item(item_id: int, quantity: int, unit_price: str) -> ReceiptItem:
    price = Decimal(unit_price)
    return ReceiptItem(
        inventory_item_id=item_id,
        quantity=quantity,
        unit_price=price,
        total_price=price * quantity,
    )


def seed_receipts(
    receipts: ReceiptRepository, user_id: int, items: dict[str, int]
) -> None:
    samples = [
        Receipt(
            user_id=user_id,
            receipt_number="OR-0001",
            original_image_path="sample_receipts/or-0001.jpg",
            purchase_date=date(2026, 9, 3),
            total_amount=Decimal(0),
            payer_name="St. Luke's Medical Center",
            payer_address="279 E. Rodriguez Sr. Ave., Quezon City",
            payment_method="CASH",
            items=[
                receipt_item(items["Pedicle Screw 6.5mm"], 8, "4500.00"),
                receipt_item(items["Titanium Rod 5.5mm"], 2, "6200.00"),
            ],
        ),
        Receipt(
            user_id=user_id,
            receipt_number="OR-0002",
            original_image_path="sample_receipts/or-0002.jpg",
            purchase_date=date(2026, 9, 17),
            total_amount=Decimal(0),
            payer_name="The Medical City",
            payment_method="CHECK",
            check_number="0004521",
            bank_branch="BDO Ortigas",
            items=[
                receipt_item(items["Bone Graft Substitute 5cc"], 3, "8750.00"),
                receipt_item(items["Sterile Gauze Pack"], 20, "85.50"),
            ],
        ),
        Receipt(
            user_id=user_id,
            receipt_number="OR-0003",
            original_image_path="sample_receipts/or-0003.jpg",
            purchase_date=date(2026, 10, 2),
            total_amount=Decimal(0),
            payer_name="St. Luke's Medical Center",
            payment_method="CASH",
            items=[receipt_item(items["Surgical Gloves (box)"], 10, "420.00")],
        ),
    ]
    for receipt in samples:
        receipt.total_amount = sum(
            (item.total_price for item in receipt.items), Decimal(0)
        )
        if not receipts.is_duplicate(receipt):
            receipts.add(receipt)


def main() -> None:
    upgrade()

    admin_id = seed_users(RoleRepository(), UserRepository())
    item_ids = seed_inventory(
        ProductTypeRepository(), SupplierRepository(), InventoryItemRepository()
    )
    receipts = ReceiptRepository()
    seed_receipts(receipts, admin_id, item_ids)

    print(
        f"seeded: {UserRepository().count()} users, "
        f"{InventoryItemRepository().count()} inventory items, "
        f"{receipts.count()} receipts"
    )


if __name__ == "__main__":
    main()
