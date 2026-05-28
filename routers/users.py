from fastapi import APIRouter, Depends, HTTPException, File, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from pathlib import Path
import shutil
from database import get_db
from models import User, Candidate
from schemas import UserOut, UserUpdate, MessageResponse
from dependencies import get_current_user, require_role, get_current_candidate
from services.resume_parser import extract_text_from_pdf
from tasks.matching import embed_candidate
import uuid
import os

router = APIRouter(prefix="/users", tags=["users"])

@router.get("/me", response_model=UserOut)
async def get_me(current_user: User = Depends(get_current_user)):
    return current_user

@router.put("/me", response_model=UserOut)
async def update_me(update: UserUpdate, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    if update.full_name is not None:
        current_user.full_name = update.full_name
    if update.email is not None:
        # Check if email already taken
        existing = await db.execute(select(User).where(User.email == update.email, User.id != current_user.id))
        if existing.scalar_one_or_none():
            raise HTTPException(status_code=400, detail="Email already used")
        current_user.email = update.email
    await db.commit()
    await db.refresh(current_user)
    return current_user

@router.get("/{user_id}", response_model=UserOut)
async def get_user(user_id: uuid.UUID, db: AsyncSession = Depends(get_db), _=Depends(require_role("admin"))):
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user

@router.patch("/{user_id}/deactivate", response_model=MessageResponse)
async def deactivate_user(user_id: uuid.UUID, db: AsyncSession = Depends(get_db), _=Depends(require_role("admin"))):
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    user.is_active = False
    await db.commit()
    return {"message": "User deactivated"}

@router.post("/me/resume")
async def upload_resume(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)  # 1. Changed type-hint from Session to AsyncSession
):
    # Validate it's a PDF extension
    if not (file.filename or "").lower().endswith('.pdf'):
        raise HTTPException(status_code=400, detail="Only PDF files are supported.")

    # Read the file contents into memory (once)
    file_bytes = await file.read()
    
    if not file_bytes:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")

    try:
        # 2. Parse text using the in-memory bytes
        parsed_text = extract_text_from_pdf(file_bytes)
        
        # 3. Asynchronously fetch the candidate profile matching current_user.id
        result = await db.execute(select(Candidate).where(Candidate.user_id == current_user.id))
        candidate = result.scalar_one_or_none()
        
        # 4. FIX: If the candidate profile record is missing from the database, create it now!
        if not candidate:
            candidate = Candidate(
                user_id=current_user.id,
                skills="",
                experience_years=0,
                bio=""
            )
            db.add(candidate)
            await db.flush()  # Populates candidate.id for downstream use
        
        # 5. Save a copy of the PDF file to local static directory
        os.makedirs("static/resumes", exist_ok=True)
        file_path = f"static/resumes/{current_user.id}.pdf"
        with open(file_path, "wb") as f:
            f.write(file_bytes)
            
        # 6. Update the candidate instance fields
        candidate.resume_url = f"/static/resumes/{current_user.id}.pdf"
        candidate.resume_text = parsed_text
        
        # 7. Asynchronously commit the changes to your Postgres DB
        await db.commit()

        # 8. Trigger your celery task to embed the candidate background vectors
        embed_candidate.delay(str(candidate.id))

        return {"message": "Resume uploaded and processed successfully"}

    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=400, detail=f"Failed to process resume: {str(e)}")