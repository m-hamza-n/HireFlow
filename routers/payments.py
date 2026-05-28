from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from uuid import UUID
from database import get_db
from models import Company, User, Payment
from dependencies import get_current_active_user, require_role
from services.payment_service import create_checkout_session, confirm_payment, PLANS

router = APIRouter(prefix="/payments", tags=["payments"])

class CheckoutRequest(BaseModel):
    plan: str  # "basic" or "pro"

@router.post("/checkout")
async def checkout(
    req: CheckoutRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("recruiter"))
):
    """Create a simulated checkout session."""
    # Find the recruiter's company (assuming one company per recruiter for simplicity)
    result = await db.execute(select(Company).where(Company.owner_id == current_user.id))
    company = result.scalar_one_or_none()
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")
    try:
        session_data = await create_checkout_session(company.id, req.plan, db)
        return session_data
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/confirm/{session_id}")
async def confirm(
    session_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("recruiter"))
):
    """Confirm payment and activate plan."""
    try:
        payment = await confirm_payment(session_id, db)
        return {"message": f"Plan {payment.plan} activated successfully"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/history")
async def payment_history(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("recruiter"))
):
    """Get payment history for the recruiter's company."""
    result = await db.execute(select(Company).where(Company.owner_id == current_user.id))
    company = result.scalar_one_or_none()
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")
    payments_result = await db.execute(select(Payment).where(Payment.company_id == company.id).order_by(Payment.created_at.desc()))
    payments = payments_result.scalars().all()
    return [
        {
            "id": str(p.id),
            "plan": p.plan,
            "amount_cents": p.amount_cents,
            "status": p.status,
            "created_at": p.created_at,
            "completed_at": p.completed_at,
        }
        for p in payments
    ]

@router.get("/plans")
async def list_plans():
    """Public endpoint to list available plans and prices."""
    return {
        "basic": {"price": 29, "currency": "USD", "max_active_jobs": 5},
        "pro": {"price": 99, "currency": "USD", "max_active_jobs": "unlimited"}
    }