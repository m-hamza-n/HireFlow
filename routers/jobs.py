from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_
from database import get_db
from models import Job, Company, User
from schemas import JobCreate, JobUpdate, JobOut
from dependencies import get_current_active_user, require_role
from uuid import UUID
from tasks.matching import embed_job

router = APIRouter(prefix="/jobs", tags=["jobs"])


# ---------- /search MUST come before /{job_id} ----------

@router.get("/search")
async def search_jobs(
    q: str = Query(..., min_length=1),
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    query = select(Job).where(
        or_(
            Job.title.ilike(f"%{q}%"),
            Job.description.ilike(f"%{q}%")
        ),
        Job.status == "active"
    ).offset(skip).limit(limit)
    result = await db.execute(query)
    return result.scalars().all()


@router.post("/", response_model=JobOut, status_code=201)
async def create_job(
    job_data: JobCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("recruiter"))
):
    result = await db.execute(select(Company).where(Company.id == job_data.company_id))
    company = result.scalar_one_or_none()
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")
    if company.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not the owner")

    if company.plan == "free":
        raise HTTPException(status_code=402, detail="Free plan cannot post jobs. Upgrade to continue.")
    if company.plan == "basic":
        active_jobs_result = await db.execute(
            select(Job).where(Job.company_id == company.id, Job.status.in_(["draft", "active"]))
        )
        if len(active_jobs_result.scalars().all()) >= 5:
            raise HTTPException(status_code=402, detail="Basic plan limited to 5 active jobs. Upgrade or close some jobs.")

    new_job = Job(
        title=job_data.title,
        description=job_data.description,
        requirements=job_data.requirements,
        company_id=company.id,
        posted_by=current_user.id,
        status=job_data.status or "draft",
        job_type=job_data.job_type,
        location=job_data.location,
        salary_min=job_data.salary_min,
        salary_max=job_data.salary_max
    )
    db.add(new_job)
    await db.commit()
    await db.refresh(new_job)
    embed_job.delay(str(new_job.id))
    return new_job


@router.get("/", response_model=list[JobOut])
async def list_jobs(
    location: Optional[str] = None,
    job_type: Optional[str] = None,
    salary_min: Optional[int] = None,
    salary_max: Optional[int] = None,
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    query = select(Job).where(Job.status == "active")
    if location:
        query = query.where(Job.location.ilike(f"%{location}%"))
    if job_type:
        query = query.where(Job.job_type == job_type)
    if salary_min is not None:
        query = query.where(Job.salary_min >= salary_min)
    if salary_max is not None:
        query = query.where(Job.salary_max <= salary_max)
    query = query.offset(skip).limit(limit)
    result = await db.execute(query)
    return result.scalars().all()


@router.get("/{job_id}", response_model=JobOut)
async def get_job(
    job_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    result = await db.execute(select(Job).where(Job.id == job_id))
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@router.put("/{job_id}", response_model=JobOut)
async def update_job(
    job_id: UUID,
    update_data: JobUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    result = await db.execute(select(Job).where(Job.id == job_id))
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    company_result = await db.execute(select(Company).where(Company.id == job.company_id))
    company = company_result.scalar_one()
    if job.posted_by != current_user.id and company.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized")
    for field, value in update_data.model_dump(exclude_unset=True).items():
        setattr(job, field, value)
    await db.commit()
    await db.refresh(job)
    embed_job.delay(str(job.id))
    return job


@router.delete("/{job_id}", status_code=204)
async def delete_job(
    job_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    result = await db.execute(select(Job).where(Job.id == job_id))
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    company_result = await db.execute(select(Company).where(Company.id == job.company_id))
    company = company_result.scalar_one()
    if job.posted_by != current_user.id and company.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized")
    await db.delete(job)
    await db.commit()


@router.patch("/{job_id}/status", response_model=JobOut)
async def change_job_status(
    job_id: UUID,
    status: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    if status not in ["draft", "active", "closed"]:
        raise HTTPException(status_code=400, detail="Invalid status")
    result = await db.execute(select(Job).where(Job.id == job_id))
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    company_result = await db.execute(select(Company).where(Company.id == job.company_id))
    company = company_result.scalar_one()
    if job.posted_by != current_user.id and company.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized")
    job.status = status
    await db.commit()
    await db.refresh(job)
    return job