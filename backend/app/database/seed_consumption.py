"""Synthetic demo consumption history.

Run from the backend folder:  python -m app.database.seed_consumption

Adds 120 days of synthetic consumption records (enough for every 90-day forecast window) for every active item. It does
NOT change on-hand quantities: stock levels are set on the inventory records
themselves. Synthetic data only; never run against a database holding real
business records.
"""
from datetime import date, timedelta
from decimal import Decimal
import random

from sqlalchemy import select

from app.database.session import SessionLocal
from app.models import InventoryItem, InventoryConsumption


def seed_consumption_history():
    db = SessionLocal()
    rng = random.Random(42)

    today = date.today()
    end_date = today - timedelta(days=1)
    start_date = today - timedelta(days=120)

    inserted = 0
    skipped = 0

    try:
        items = db.scalars(
            select(InventoryItem).where(InventoryItem.is_active.is_(True))
        ).all()

        if not items:
            print("No active inventory items found.")
            return

        for item in items:
            # Find dates that already have consumption records.
            existing_dates = set(
                db.scalars(
                    select(InventoryConsumption.consumption_date).where(
                        InventoryConsumption.inventory_item_id == item.id,
                        InventoryConsumption.consumption_date >= start_date,
                        InventoryConsumption.consumption_date <= end_date,
                    )
                ).all()
            )

            current_date = start_date

            while current_date <= end_date:
                # Never create a second record for an existing date.
                if current_date in existing_dates:
                    skipped += 1
                    current_date += timedelta(days=1)
                    continue

                # Estimate a realistic daily usage baseline.
                baseline = max(float(item.reorder_level) / 12, 5)

                # Weekends generally have lower production consumption.
                if current_date.weekday() >= 5:
                    multiplier = rng.uniform(0.15, 0.45)
                else:
                    multiplier = rng.uniform(0.75, 1.25)

                quantity = Decimal(
                    str(round(baseline * multiplier, 3))
                )

                reference = (
                    f"DEMO-HIST-{item.item_code}-"
                    f"{current_date.strftime('%Y%m%d')}"
                )

                record = InventoryConsumption(
                    inventory_item_id=item.id,
                    consumption_date=current_date,
                    quantity_consumed=quantity,
                    reference=reference,
                    notes="Synthetic historical consumption for Inventra demo",
                )

                db.add(record)
                inserted += 1

                current_date += timedelta(days=1)

        # Save historical records only.
        # Deliberately do not modify inventory on-hand quantities.
        db.commit()

        print("\nHistorical consumption seeding completed!")
        print(f"Active inventory items: {len(items)}")
        print(f"Records inserted: {inserted}")
        print(f"Existing dates skipped: {skipped}")
        print(f"History period: {start_date} to {end_date}")
        print("Inventory quantities were not changed.")

    except Exception:
        db.rollback()
        raise

    finally:
        db.close()


if __name__ == "__main__":
    seed_consumption_history()
