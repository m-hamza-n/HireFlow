import logging
from tasks.celery_app import celery_app
from tasks.sync_db import SyncSessionLocal
from models import Job, Candidate
from services.gemini import get_embedding
from services.chromadb_service import get_or_create_collection, upsert_document

logger = logging.getLogger(__name__)

def build_job_text(job):
    return f"{job.title}. {job.description}. Requirements: {job.requirements}"

@celery_app.task
def embed_job(job_id: str):
    session = SyncSessionLocal()
    try:
        job = session.query(Job).filter(Job.id == job_id).first()
        if not job:
            logger.error(f"Job {job_id} not found")
            return
        text = build_job_text(job)
        embedding = get_embedding(text)
        if embedding is None:
            logger.error(f"Failed to get embedding for job {job_id}")
            return
        collection = get_or_create_collection("jobs")
        doc_id = f"job_{job_id}"
        metadata = {"job_id": str(job.id), "company_id": str(job.company_id), "status": job.status}
        upsert_document(collection, doc_id, embedding, metadata, text)
        job.embedding_id = doc_id
        session.commit()
        logger.info(f"Embedded job {job_id}")
    except Exception as e:
        logger.exception(f"Error embedding job {job_id}: {e}")
    finally:
        session.close()

@celery_app.task
def embed_candidate(candidate_id: str):
    session = SyncSessionLocal()
    try:
        candidate = session.query(Candidate).filter(Candidate.id == candidate_id).first()
        if not candidate or not candidate.resume_text:
            logger.error(f"Candidate {candidate_id} has no resume text")
            return
        embedding = get_embedding(candidate.resume_text)
        if embedding is None:
            logger.error(f"Failed to get embedding for candidate {candidate_id}")
            return
        collection = get_or_create_collection("candidates")
        doc_id = f"candidate_{candidate_id}"
        metadata = {"user_id": str(candidate.user_id), "candidate_id": str(candidate.id)}
        upsert_document(collection, doc_id, embedding, metadata, candidate.resume_text)
        candidate.embedding_id = doc_id
        session.commit()
        logger.info(f"Embedded candidate {candidate_id}")
    except Exception as e:
        logger.exception(f"Error embedding candidate {candidate_id}: {e}")
    finally:
        session.close()