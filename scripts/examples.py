"""
Runnable examples of how the rest of the app should use the database.
Everything goes through the repositories in data/repository.py and
uses the dataclasses from core/models.py, no SQLAlchemy needed.

Runs on a throwaway in-memory database, so your real receipts.db
is never touched. In the app, create repositories with no arguments
(e.g. ReceiptRepository()) and they use the real database.

Usage:
    python scripts/examples.py
"""

from datetime import date
from decimal import Decimal

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

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
from receipt_manager.data.orm_models import Base
from receipt_manager.data.repository import (
    InventoryItemRepository,
    ProductTypeRepository,
    ReceiptFilter,
    ReceiptRepository,
    RoleRepository,
    SupplierRepository,
    UserRepository,
)


# StaticPool keeps one connection, otherwise every session would get its own empty :memory: database
def in_memory_sessions() -> sessionmaker:
    engine = create_engine("sqlite+pysqlite:///:memory:", poolclass=StaticPool)
    Base.metadata.create_all(engine)
    return sessionmaker(engine)


def main() -> None:
    sessions = in_memory_sessions()
    roles = RoleRepository(sessions)
    users = UserRepository(sessions)
    product_types = ProductTypeRepository(sessions)
    suppliers = SupplierRepository(sessions)
    items = InventoryItemRepository(sessions)
    receipts = ReceiptRepository(sessions)

    # Adding: add() returns a copy with the new id filled in

    staff_role = roles.add(Role(name="Staff"))
    user = users.add(
        User(
            role_id=staff_role.id,
            fullname="Juan Dela Cruz",
            # user_id is filled in when the user is inserted, the password should be a hash
            login=Login(user_id=0, username="juan", password="scrypt$..."),
        )
    )
    print("added user", user.id, user.fullname)

    implants = product_types.add(ProductType(name="Implants"))
    # names are unique, so check before adding another one
    print("'implants' taken:", product_types.name_exists("implants"))
    supplier = suppliers.add(Supplier(name="SpineCare Distributors"))

    screw = items.add(
        InventoryItem(
            product_type_id=implants.id,
            supplier_id=supplier.id,
            name="Pedicle Screw 6.5mm",
            stock_ledger=StockLedger(inventory_item_id=0, current_quantity=120),
        )
    )
    print("added item", screw.name, "stock:", screw.stock_ledger.current_quantity)

    # A receipt and its items are saved together

    for number, day, quantity, payer in [
        ("OR-0001", date(2026, 9, 3), 8, "St. Luke's Medical Center"),
        ("OR-0002", date(2026, 9, 17), 2, "The Medical City"),
        ("OR-0003", date(2026, 10, 2), 5, "St. Luke's Medical Center"),
    ]:
        price = Decimal("4500.00")
        receipts.add(
            Receipt(
                user_id=user.id,
                receipt_number=number,
                original_image_path=f"sample_receipts/{number.lower()}.jpg",
                purchase_date=day,
                total_amount=price * quantity,
                payer_name=payer,
                payment_method="CASH",
                items=[
                    ReceiptItem(
                        inventory_item_id=screw.id,
                        quantity=quantity,
                        unit_price=price,
                        total_price=price * quantity,
                    )
                ],
            )
        )

    # Getting: get() returns None when the id doesn't exist

    first = receipts.get(1)
    print(
        "receipt 1:",
        first.receipt_number,
        first.total_amount,
        len(first.items),
        "item(s)",
    )
    print("receipt 999:", receipts.get(999))
    print("login lookup:", users.get_by_username("juan").fullname)

    # Filtering and sorting: fields left as None are ignored, the rest must all match

    september = ReceiptFilter(year=2026, month=9)
    print("September receipts:", [r.receipt_number for r in receipts.find(september)])

    st_lukes = ReceiptFilter(text="luke", min_amount=Decimal(10000))
    print(
        "St. Luke's over 10,000:", [r.receipt_number for r in receipts.find(st_lukes)]
    )

    # newest first is the default, sort_by only accepts the columns in _SORTABLE
    biggest = receipts.find(sort_by="total_amount", descending=True, limit=2)
    print("2 biggest:", [(r.receipt_number, r.total_amount) for r in biggest])

    # paging, e.g. "showing 1-2 of 3"
    page = receipts.find(limit=2, offset=0)
    print(f"showing {len(page)} of {receipts.count_matching()}")

    print("September total:", receipts.total_amount(september))
    print(
        "receipts with implants:",
        receipts.count_matching(ReceiptFilter(product_type_id=implants.id)),
    )

    # Duplicates: check before saving a newly scanned receipt

    rescanned = Receipt(
        user_id=user.id,
        receipt_number="or-0001 ",  # case and spaces are ignored
        original_image_path="scan.jpg",
        purchase_date=date(2026, 9, 3),
        total_amount=Decimal("36000.00"),
        payer_name="St. Luke's Medical Center",
    )
    print(
        "duplicates of rescan:",
        [r.receipt_number for r in receipts.find_duplicates(rescanned)],
    )

    # Updating: change the dataclass, then pass it to update()

    first.payer_name = "St. Luke's Medical Center - BGC"
    first.items[0].quantity = 10
    first.items[0].total_price = first.items[0].unit_price * 10
    first.total_amount = first.items[0].total_price
    updated = receipts.update(first)
    print("updated:", updated.payer_name, updated.total_amount)

    # removing an item from the list deletes it on update
    first.items = []
    print("items after removing:", len(receipts.update(first).items))

    # Deleting: True if it existed, its items are deleted with it

    print("deleted receipt 2:", receipts.delete(2))
    print("deleted receipt 2 again:", receipts.delete(2))
    print("receipts left:", receipts.count())


if __name__ == "__main__":
    main()
