from pydantic import BaseModel, EmailStr, Field, ConfigDict
from uuid import UUID
from datetime import datetime
from typing import Optional, List

# Auth schemas
class UserRegister(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=6)
    role: str  # candidate or recruiter
    full_name: str

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"

class RefreshRequest(BaseModel):
    refresh_token: str

class AccessTokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"

# User schemas
class UserOut(BaseModel):
    id: UUID
    email: EmailStr
    role: str
    full_name: Optional[str]
    is_active: bool
    created_at: datetime

class UserUpdate(BaseModel):
    full_name: Optional[str]
    email: Optional[EmailStr]

# Common response
class MessageResponse(BaseModel):
    message: str

class CompanyBase(BaseModel):
    name: str
    description: Optional[str] = None
    website: Optional[str] = None

class CompanyCreate(CompanyBase):
    pass

class CompanyUpdate(CompanyBase):
    pass

class CompanyOut(CompanyBase):
    id: UUID
    owner_id: UUID
    plan: str
    plan_expires_at: Optional[datetime]
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)

class JobBase(BaseModel):
    title: str
    description: str
    requirements: str
    job_type: Optional[str] = None
    location: Optional[str] = None
    salary_min: Optional[int] = None
    salary_max: Optional[int] = None

class JobCreate(JobBase):
    company_id: UUID
    status: Optional[str] = "draft"

class JobUpdate(JobBase):
    status: Optional[str] = None
    # other fields optional

class JobOut(JobBase):
    id: UUID
    company_id: UUID
    posted_by: UUID
    status: str
    created_at: datetime
    updated_at: Optional[datetime]
    model_config = ConfigDict(from_attributes=True)

class ApplicationCreate(BaseModel):
    job_id: UUID
    cover_letter: Optional[str] = None

class ApplicationUpdateStatus(BaseModel):
    status: str  # pending, screening, shortlisted, rejected, hired

class ApplicationOut(BaseModel):
    id: UUID
    job_id: UUID
    candidate_id: UUID
    status: str
    cover_letter: Optional[str]
    ai_score: Optional[float]
    ai_summary: Optional[str]
    created_at: datetime
    updated_at: Optional[datetime]
    model_config = ConfigDict(from_attributes=True)