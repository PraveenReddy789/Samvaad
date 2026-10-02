import csv
import json
import glob
import sys
from pathlib import Path

# Ensure project root is in sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from backend.config import CUSTOMERS_DIR, CALLS_DIR
from backend.db.database import engine, SessionLocal, Base
from backend.db.models import Customer, Payment, CallDisposition


def seed_database():
    """Initializes tables and seeds data from synthetic CSV and JSON files."""
    print("Initializing database tables...")
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()

    try:
        # 1. Seed Customers
        customers_csv = CUSTOMERS_DIR / "customers.csv"
        if customers_csv.exists():
            with open(customers_csv, mode="r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    existing = db.query(Customer).filter(Customer.customer_id == row["customer_id"]).first()
                    if not existing:
                        customer = Customer(
                            customer_id=row["customer_id"],
                            name=row["name"],
                            mobile_number=row["mobile_number"],
                            loan_id=row["loan_id"],
                            product_id=row["product_id"],
                            emi_amount=float(row["emi_amount"]),
                            emi_due_date=row["emi_due_date"],
                            status=row["status"],
                        )
                        db.add(customer)
            db.commit()
            print("Seeded customers successfully.")

        # 2. Seed Payments
        payments_csv = CUSTOMERS_DIR / "payments.csv"
        if payments_csv.exists():
            with open(payments_csv, mode="r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    existing = db.query(Payment).filter(Payment.payment_id == row["payment_id"]).first()
                    if not existing:
                        payment = Payment(
                            payment_id=row["payment_id"],
                            customer_id=row["customer_id"],
                            loan_id=row["loan_id"],
                            payment_date=row["payment_date"],
                            amount=float(row["amount"]),
                            status=row["status"],
                            transaction_reference=row["transaction_reference"],
                        )
                        db.add(payment)
            db.commit()
            print("Seeded payments successfully.")

        # 3. Seed Past Call Dispositions
        call_files = glob.glob(str(CALLS_DIR / "*.json"))
        for call_file in call_files:
            with open(call_file, mode="r", encoding="utf-8") as f:
                data = json.load(f)
                existing = db.query(CallDisposition).filter(CallDisposition.call_id == data["call_id"]).first()
                if not existing:
                    disposition = CallDisposition(
                        call_id=data["call_id"],
                        customer_id=data["customer_id"],
                        loan_id=data.get("loan_id"),
                        timestamp=data.get("timestamp"),
                        direction=data.get("direction", "outbound"),
                        intent=data.get("intent"),
                        outcome=data.get("outcome"),
                        sentiment=data.get("sentiment", "neutral"),
                        summary=data.get("summary")
                    )
                    db.add(disposition)
        db.commit()
        print(f"Seeded {len(call_files)} past call histories successfully.")

    except Exception as e:
        db.rollback()
        print(f"Error seeding database: {e}")
        raise e
    finally:
        db.close()


if __name__ == "__main__":
    seed_database()
