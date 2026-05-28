import uuid
from datetime import datetime, timedelta, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from models import Payment, Company

PLANS = {
    "basic": {"price_cents": 2900, "max_jobs": 5},
    "pro": {"price_cents": 9900, "max_jobs": None}  # None = unlimited
}

async def create_checkout_session(company_id: uuid.UUID, plan: str, db: AsyncSession):
    """Create a simulated checkout session."""
    if plan not in PLANS:
        raise ValueError("Invalid plan")
    session_id = str(uuid.uuid4())
    amount_cents = PLANS[plan]["price_cents"]
    payment = Payment(
        company_id=company_id,
        session_id=session_id,
        amount_cents=amount_cents,
        plan=plan,
        status="pending"
    )
    db.add(payment)
    await db.commit()
    await db.refresh(payment)
    return {
        "session_id": session_id,
        "plan": plan,
        "amount_cents": amount_cents,
        "message": f"Use /payments/confirm/{session_id} to complete payment"
    }

async def confirm_payment(session_id: str, db: AsyncSession):
    """Confirm a pending payment and activate the plan for the company."""
    # Get payment
    result = await db.execute(select(Payment).where(Payment.session_id == session_id))
    payment = result.scalar_one_or_none()
    if not payment:
        raise ValueError("Payment session not found")
    if payment.status != "pending":
        raise ValueError("Payment already processed")
    # Update payment
    payment.status = "completed"
    payment.completed_at = datetime.utcnow()
    # Update company plan
    result = await db.execute(select(Company).where(Company.id == payment.company_id))
    company = result.scalar_one()
    company.plan = payment.plan
    company.plan_expires_at = datetime.utcnow() + timedelta(days=30)
    await db.commit()
    await db.refresh(payment)
    return payment