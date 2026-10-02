from datetime import datetime
from sqlalchemy import Column, String, Float, Boolean, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship
from backend.db.database import Base


class Customer(Base):
    __tablename__ = "customers"

    customer_id = Column(String(50), primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    mobile_number = Column(String(20), nullable=False, index=True)
    loan_id = Column(String(50), nullable=False, index=True)
    product_id = Column(String(50), nullable=False)
    emi_amount = Column(Float, nullable=False)
    emi_due_date = Column(String(20), nullable=False)
    status = Column(String(50), nullable=False)  # OVERDUE, DUE_TODAY, PAYMENT_REPORTED, SETTLED
    
    # Dynamic recovery tracking fields
    promise_to_pay_date = Column(String(20), nullable=True)
    hardship_flag = Column(Boolean, default=False)
    hardship_reason = Column(Text, nullable=True)
    notes = Column(Text, nullable=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    payments = relationship("Payment", back_populates="customer", cascade="all, delete-orphan")
    escalations = relationship("Escalation", back_populates="customer", cascade="all, delete-orphan")
    dispositions = relationship("CallDisposition", back_populates="customer", cascade="all, delete-orphan")


class Payment(Base):
    __tablename__ = "payments"

    payment_id = Column(String(50), primary_key=True, index=True)
    customer_id = Column(String(50), ForeignKey("customers.customer_id"), nullable=False, index=True)
    loan_id = Column(String(50), nullable=False)
    payment_date = Column(String(20), nullable=False)
    amount = Column(Float, nullable=False)
    status = Column(String(50), nullable=False)  # SUCCESS, PENDING, FAILED
    transaction_reference = Column(String(100), nullable=False, index=True)

    customer = relationship("Customer", back_populates="payments")


class Escalation(Base):
    __tablename__ = "escalations"

    escalation_id = Column(String(50), primary_key=True, index=True)
    customer_id = Column(String(50), ForeignKey("customers.customer_id"), nullable=False)
    loan_id = Column(String(50), nullable=True)
    category = Column(String(100), nullable=False)  # PAYMENT_DISPUTE, HARDSHIP, FRAUD, LEGAL, HUMAN_REQUEST
    reason = Column(Text, nullable=False)
    status = Column(String(50), default="OPEN")  # OPEN, IN_REVIEW, RESOLVED
    created_at = Column(DateTime, default=datetime.utcnow)

    customer = relationship("Customer", back_populates="escalations")


class CallDisposition(Base):
    __tablename__ = "call_dispositions"

    call_id = Column(String(50), primary_key=True, index=True)
    customer_id = Column(String(50), ForeignKey("customers.customer_id"), nullable=False)
    loan_id = Column(String(50), nullable=True)
    timestamp = Column(String(50), default=lambda: datetime.utcnow().isoformat())
    direction = Column(String(20), default="outbound")
    intent = Column(String(100), nullable=True)
    outcome = Column(String(100), nullable=False)  # ALREADY_PAID, WILL_PAY, HARDSHIP, DISPUTE, ESCALATED, REFUSAL_TO_PAY
    sentiment = Column(String(50), default="neutral")
    summary = Column(Text, nullable=True)

    customer = relationship("Customer", back_populates="dispositions")
