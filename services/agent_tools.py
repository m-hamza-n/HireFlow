import logging
from typing import List, Dict, Any, Optional
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_
from models import Job, Company, Application, Candidate, User
from services.chromadb_service import get_or_create_collection, query_collection
from services.gemini import get_embedding

logger = logging.getLogger(__name__)

async def search_jobs(
    db: AsyncSession,
    query: str,
    location: Optional[str] = None,
    job_type: Optional[str] = None
) -> List[Dict[str, Any]]:
    """Search active jobs by keyword, location, type."""
    stmt = select(Job, Company.name.label("company_name")).join(Company, Job.company_id == Company.id).where(Job.status == "active")
    if query:
        stmt = stmt.where(
            or_(
                Job.title.ilike(f"%{query}%"),
                Job.description.ilike(f"%{query}%"),
                Job.requirements.ilike(f"%{query}%")
            )
        )
    if location:
        stmt = stmt.where(Job.location.ilike(f"%{location}%"))
    if job_type:
        stmt = stmt.where(Job.job_type == job_type)
    stmt = stmt.limit(10)
    result = await db.execute(stmt)
    rows = result.all()
    return [
        {
            "id": str(job.id),
            "title": job.title,
            "company": company_name,
            "location": job.location,
            "job_type": job.job_type,
            "salary_min": job.salary_min,
            "salary_max": job.salary_max,
        }
        for job, company_name in rows
    ]

async def get_job_details(db: AsyncSession, job_id: str) -> Optional[Dict[str, Any]]:
    """Fetch full job details by ID."""
    stmt = select(Job, Company.name.label("company_name")).join(Company, Job.company_id == Company.id).where(Job.id == UUID(job_id))
    result = await db.execute(stmt)
    row = result.first()
    if not row:
        return None
    job, company_name = row
    return {
        "id": str(job.id),
        "title": job.title,
        "description": job.description,
        "requirements": job.requirements,
        "company": company_name,
        "location": job.location,
        "job_type": job.job_type,
        "salary_min": job.salary_min,
        "salary_max": job.salary_max,
        "status": job.status,
    }

async def get_application_status(db: AsyncSession, candidate_id: str) -> List[Dict[str, Any]]:
    """Get all applications for a candidate with job titles and statuses."""
    stmt = select(Application, Job.title, Company.name).join(Job, Application.job_id == Job.id).join(Company, Job.company_id == Company.id).where(Application.candidate_id == UUID(candidate_id))
    result = await db.execute(stmt)
    apps = result.all()
    return [
        {
            "job_title": job_title,
            "company": company_name,
            "status": app.status,
            "ai_score": app.ai_score,
            "applied_at": app.created_at.isoformat() if app.created_at else None,
        }
        for app, job_title, company_name in apps
    ]

async def search_knowledge_base(query: str) -> str:
    """Search the hiring knowledge base using ChromaDB and return top 3 chunks."""
    embedding = get_embedding(query)
    if not embedding:
        return "Knowledge base unavailable."
    collection = get_or_create_collection("knowledge_base")
    try:
        results = query_collection(collection, embedding, n_results=3)
        chunks = results.get("documents", [[]])[0]
        return "\n\n".join(chunks) if chunks else "No relevant info found."
    except Exception as e:
        logger.exception(f"Knowledge base search error: {e}")
        return "Error accessing knowledge base."

async def get_top_candidates(db: AsyncSession, job_id: str, limit: int = 5) -> List[Dict[str, Any]]:
    """Get top matching candidates for a job (same logic as /ai/match)."""
    from services.ai_matching import match_candidates_for_job
    return await match_candidates_for_job(db, UUID(job_id), limit)