from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from typing import List, Dict, Any
from uuid import UUID

from database import get_db
from models import Job, Candidate, User
from dependencies import get_current_active_user, require_role, get_current_candidate
from services.gemini import chat_with_tools, get_embedding
from services.chromadb_service import get_or_create_collection, upsert_document
from services.ai_matching import match_candidates_for_job
from tasks.screening import screen_application
from tasks.matching import embed_candidate

router = APIRouter(prefix="/ai", tags=["ai"])

# ---------- Request/Response Schemas ----------
class ChatRequest(BaseModel):
    messages: List[Dict[str, str]]  # [{"role": "user", "content": "..."}]

class ChatResponse(BaseModel):
    reply: str
    tool_calls_made: List[str]

# ---------- Endpoints ----------
@router.get("/match/{job_id}")
async def match_candidates(
    job_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("recruiter"))
):
    """Get top matched candidates for a job (recruiter only)."""
    # Verify recruiter owns the job's company
    job_result = await db.execute(select(Job).where(Job.id == job_id))
    job = job_result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    from models import Company
    company_result = await db.execute(select(Company).where(Company.id == job.company_id))
    company = company_result.scalar_one()
    if company.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not your job")
    
    matches = await match_candidates_for_job(db, job_id, limit=10)
    return matches

@router.post("/screen/{application_id}")
async def manual_screen(
    application_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("recruiter"))
):
    """Manually re-trigger AI screening for an application."""
    # Optional: verify recruiter owns the job
    from models import Application
    app_result = await db.execute(select(Application).where(Application.id == application_id))
    app = app_result.scalar_one_or_none()
    if not app:
        raise HTTPException(status_code=404, detail="Application not found")
    job_result = await db.execute(select(Job).where(Job.id == app.job_id))
    job = job_result.scalar_one()
    from models import Company
    company_result = await db.execute(select(Company).where(Company.id == job.company_id))
    company = company_result.scalar_one()
    if company.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized")
    
    screen_application.delay(str(application_id), force=True)
    return {"message": "Screening task triggered"}

@router.post("/chat", response_model=ChatResponse)
async def agent_chat(
    req: ChatRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Agentic chatbot with tool-use."""
    result = await chat_with_tools(
        messages=req.messages,
        user_id=str(current_user.id),
        user_role=current_user.role,
        db=db
    )
    return result

@router.post("/embed/resume")
async def embed_own_resume(
    db: AsyncSession = Depends(get_db),
    candidate: Candidate = Depends(get_current_candidate)
):
    """Re-embed the candidate's resume into ChromaDB."""
    if not candidate.resume_text:
        raise HTTPException(status_code=400, detail="No resume text found. Upload resume first.")
    embed_candidate.delay(str(candidate.id))
    return {"message": "Resume embedding task started"}