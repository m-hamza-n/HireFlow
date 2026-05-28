from tasks.screening import screen_application
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from database import get_db
from models import Application, Job, Candidate, User, Company
from schemas import ApplicationCreate, ApplicationOut, ApplicationUpdateStatus
from dependencies import get_current_active_user, get_current_candidate, require_role
from uuid import UUID

router = APIRouter(prefix="/applications", tags=["applications"])

@router.post("/", response_model=ApplicationOut, status_code=201)
async def apply_to_job(
    application_data: ApplicationCreate,
    db: AsyncSession = Depends(get_db),
    candidate: Candidate = Depends(get_current_candidate)
):
    # Check job exists and is active
    job_result = await db.execute(select(Job).where(Job.id == application_data.job_id))
    job = job_result.scalar_one_or_none()
    if not job or job.status != "active":
        raise HTTPException(status_code=404, detail="Job not active or not found")
    
    # Check duplicate application
    existing = await db.execute(
        select(Application).where(
            and_(
                Application.job_id == application_data.job_id,
                Application.candidate_id == candidate.id
            )
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Already applied to this job")
    
    new_app = Application(
        job_id=application_data.job_id,
        candidate_id=candidate.id,
        cover_letter=application_data.cover_letter,
        status="pending"  # no AI screening yet
    )
    db.add(new_app)
    await db.commit()
    await db.refresh(new_app)

    screen_application.delay(str(new_app.id))
    return new_app

@router.get("/mine", response_model=list[ApplicationOut])
async def my_applications(
    db: AsyncSession = Depends(get_db),
    candidate: Candidate = Depends(get_current_candidate)
):
    result = await db.execute(select(Application).where(Application.candidate_id == candidate.id))
    apps = result.scalars().all()
    return apps

@router.get("/job/{job_id}", response_model=list[ApplicationOut])
async def get_job_applications(
    job_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("recruiter"))
):
    # Verify recruiter owns the company that posted the job
    job_result = await db.execute(select(Job).where(Job.id == job_id))
    job = job_result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    company_result = await db.execute(select(Company).where(Company.id == job.company_id))
    company = company_result.scalar_one()
    if company.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not your job")
    result = await db.execute(select(Application).where(Application.job_id == job_id))
    apps = result.scalars().all()
    return apps

@router.get("/{application_id}", response_model=ApplicationOut)
async def get_application(
    application_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    result = await db.execute(select(Application).where(Application.id == application_id))
    app = result.scalar_one_or_none()
    if not app:
        raise HTTPException(status_code=404, detail="Application not found")
    # Check permissions: candidate who applied or recruiter of the job's company
    candidate_result = await db.execute(select(Candidate).where(Candidate.user_id == current_user.id))
    candidate = candidate_result.scalar_one_or_none()
    if candidate and candidate.id == app.candidate_id:
        return app
    # Recruiter check
    job_result = await db.execute(select(Job).where(Job.id == app.job_id))
    job = job_result.scalar_one()
    company_result = await db.execute(select(Company).where(Company.id == job.company_id))
    company = company_result.scalar_one()
    if company.owner_id == current_user.id:
        return app
    raise HTTPException(status_code=403, detail="Not authorized")

@router.patch("/{application_id}/status", response_model=ApplicationOut)
async def update_application_status(
    application_id: UUID,
    status_update: ApplicationUpdateStatus,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("recruiter"))
):
    result = await db.execute(select(Application).where(Application.id == application_id))
    app = result.scalar_one_or_none()
    if not app:
        raise HTTPException(status_code=404, detail="Application not found")
    # Verify recruiter owns the job's company
    job_result = await db.execute(select(Job).where(Job.id == app.job_id))
    job = job_result.scalar_one()
    company_result = await db.execute(select(Company).where(Company.id == job.company_id))
    company = company_result.scalar_one()
    if company.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized")
    app.status = status_update.status
    await db.commit()
    await db.refresh(app)
    return app

@router.delete("/{application_id}", status_code=204)
async def withdraw_application(
    application_id: UUID,
    db: AsyncSession = Depends(get_db),
    candidate: Candidate = Depends(get_current_candidate)
):
    result = await db.execute(select(Application).where(Application.id == application_id))
    app = result.scalar_one_or_none()
    if not app or app.candidate_id != candidate.id:
        raise HTTPException(status_code=404, detail="Application not found or not yours")
    if app.status != "pending":
        raise HTTPException(status_code=400, detail="Cannot withdraw after screening started")
    await db.delete(app)
    await db.commit()
    return