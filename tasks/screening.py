import logging
import json
from tasks.celery_app import celery_app
from tasks.sync_db import SyncSessionLocal
from models import Application, Job, Candidate
from services.gemini import chat_completion
from tasks.notifications import notify_user

logger = logging.getLogger(__name__)

SCREENING_PROMPT_TEMPLATE = """You are a senior technical recruiter. Evaluate this application strictly and objectively.

Job Title: {title}
Job Requirements: {requirements}
Job Description: {description}

Candidate Resume:
{resume_text}

Cover Letter:
{cover_letter}

Respond ONLY with valid JSON, no markdown, no explanation:
{{
  "score": <float 0.0 to 1.0>,
  "summary": "<2-3 sentence fit assessment>",
  "strengths": ["<strength 1>", "<strength 2>"],
  "gaps": ["<gap 1>", "<gap 2>"],
  "recommendation": "<shortlist|reject|review>"
}}"""

@celery_app.task
def screen_application(application_id: str, force: bool = False):
    session = SyncSessionLocal()
    try:
        app = session.query(Application).filter(Application.id == application_id).first()
        if not app:
            return
        if not force and app.status != "pending":
            return
        app.status = "screening"
        session.commit()
        job = session.query(Job).filter(Job.id == app.job_id).first()
        candidate = session.query(Candidate).filter(Candidate.id == app.candidate_id).first()
        if not job or not candidate:
            return
        prompt = SCREENING_PROMPT_TEMPLATE.format(
            title=job.title,
            requirements=job.requirements,
            description=job.description,
            resume_text=candidate.resume_text or "",
            cover_letter=app.cover_letter or ""
        )
        response = chat_completion(prompt)
        if not response:
            return
        # Parse JSON
        try:
            if "```json" in response:
                json_str = response.split("```json")[1].split("```")[0].strip()
            elif "```" in response:
                json_str = response.split("```")[1].split("```")[0].strip()
            else:
                json_str = response.strip()
            result = json.loads(json_str)
            score = result.get("score", 0.0)
            summary = result.get("summary", "")
        except Exception:
            return
        app.ai_score = score
        app.ai_summary = summary
        if score >= 0.75:
            app.status = "shortlisted"
        elif score < 0.35:
            app.status = "rejected"
        else:
            app.status = "screening"
        session.commit()
        notify_user.delay(str(candidate.user_id), "Application Update",
                         f"Your application for {job.title} has been {app.status}.",
                         "application_update")
    except Exception as e:
        logger.exception(f"Screening error: {e}")
        session.rollback()
    finally:
        session.close()