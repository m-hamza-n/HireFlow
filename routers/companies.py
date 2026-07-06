from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from database import get_db
from models import Company, User
from schemas import CompanyCreate, CompanyUpdate, CompanyOut
from dependencies import get_current_active_user, require_role
from uuid import UUID

router = APIRouter(prefix="/companies", tags=["companies"])

@router.post("/", response_model=CompanyOut, status_code=201)
async def create_company(
    company_data: CompanyCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("recruiter"))
):
    new_company = Company(
        name=company_data.name,
        description=company_data.description,
        website=company_data.website,
        owner_id=current_user.id,
        plan="free"
    )
    db.add(new_company)
    await db.commit()
    await db.refresh(new_company)
    return new_company

@router.get("/", response_model=list[CompanyOut])
async def list_companies(
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    result = await db.execute(select(Company).offset(skip).limit(limit))
    companies = result.scalars().all()
    return companies

@router.get("/{company_id}", response_model=CompanyOut)
async def get_company(
    company_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    result = await db.execute(select(Company).where(Company.id == company_id))
    company = result.scalar_one_or_none()
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")
    return company

@router.put("/{company_id}", response_model=CompanyOut)
async def update_company(
    company_id: UUID,
    update_data: CompanyUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    result = await db.execute(select(Company).where(Company.id == company_id))
    company = result.scalar_one_or_none()
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")
    if company.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not the owner")
    if update_data.name is not None:
        company.name = update_data.name
    if update_data.description is not None:
        company.description = update_data.description
    if update_data.website is not None:
        company.website = update_data.website
    await db.commit()
    await db.refresh(company)
    return company

@router.delete("/{company_id}", status_code=204)
async def delete_company(
    company_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    result = await db.execute(select(Company).where(Company.id == company_id))
    company = result.scalar_one_or_none()
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")
    if company.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not the owner")
    await db.delete(company)
    await db.commit()
    return
