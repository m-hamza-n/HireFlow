from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from models import Job, Candidate, User
from services.gemini import get_embedding
from services.chromadb_service import get_or_create_collection, query_collection

async def match_candidates_for_job(db: AsyncSession, job_id: UUID, limit: int = 10):
    # Fetch job
    job_result = await db.execute(select(Job).where(Job.id == job_id))
    job = job_result.scalar_one_or_none()
    if not job:
        return []
    # Build job text
    job_text = f"{job.title}. {job.description}. Requirements: {job.requirements}"
    embedding = get_embedding(job_text)
    if not embedding:
        return []
    # Query ChromaDB
    collection = get_or_create_collection("candidates")
    results = query_collection(collection, embedding, n_results=limit)
    if not results or not results.get("ids") or not results["ids"][0]:
        return []
    candidate_ids = []
    for meta in results["metadatas"][0]:
        candidate_ids.append(UUID(meta["candidate_id"]))
    # Fetch full candidates and users
    candidates_list = []
    for cand_id, distance in zip(candidate_ids, results["distances"][0]):
        cand_result = await db.execute(select(Candidate, User).join(User, Candidate.user_id == User.id).where(Candidate.id == cand_id))
        row = cand_result.first()
        if row:
            candidate, user = row
            candidates_list.append({
                "candidate": {
                    "id": str(candidate.id),
                    "user_id": str(user.id),
                    "full_name": user.full_name,
                    "email": user.email,
                    "resume_text": candidate.resume_text[:500] if candidate.resume_text else "",
                    "skills": candidate.skills,
                    "experience_years": candidate.experience_years,
                },
                "similarity_score": 1 - distance  # ChromaDB returns distance (lower = better)
            })
    return sorted(candidates_list, key=lambda x: x["similarity_score"], reverse=True)