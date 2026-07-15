import json
import re

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..config import RESUME_DIR
from ..db import SessionLocal
from ..llm import LLMError
from ..models import Profile
from ..services import resume_parser
from ..services.resume_parser import ResumeParseError

router = APIRouter(prefix="/api/resume", tags=["resume"])


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _get_or_create_profile(db: Session) -> Profile:
    profile = db.get(Profile, 1)
    if profile is None:
        profile = Profile(id=1)
        db.add(profile)
        db.commit()
    return profile


@router.get("")
def get_profile(db: Session = Depends(get_db)):
    profile = db.get(Profile, 1)
    if profile is None or not profile.data_json:
        return {"exists": False}
    return {"exists": True, "profile": profile.to_dict()}


@router.post("")
async def upload_resume(
    file: UploadFile | None = File(default=None),
    text: str | None = Form(default=None),
    db: Session = Depends(get_db),
):
    """Upload a resume (PDF/DOCX/TXT file, or pasted text) and parse it into a profile."""
    if file is None and not (text and text.strip()):
        raise HTTPException(400, "Provide a resume file or pasted resume text.")

    resume_path = None
    filename = None
    if file is not None:
        content = await file.read()
        if len(content) > 10 * 1024 * 1024:
            raise HTTPException(400, "Resume file is larger than 10 MB.")
        try:
            resume_text = resume_parser.extract_text(file.filename or "", content)
        except ResumeParseError as e:
            raise HTTPException(400, str(e))
        safe_name = re.sub(r"[^A-Za-z0-9._-]", "_", file.filename or "resume")
        resume_path = RESUME_DIR / safe_name
        resume_path.write_bytes(content)
        filename = file.filename
    else:
        resume_text = text.strip()

    try:
        data = resume_parser.parse_resume(resume_text)
    except ResumeParseError as e:
        raise HTTPException(400, str(e))
    except LLMError as e:
        raise HTTPException(502, str(e))

    profile = _get_or_create_profile(db)
    profile.full_name = data.get("full_name")
    profile.email = data.get("email")
    profile.phone = data.get("phone")
    profile.location = data.get("location")
    profile.resume_text = resume_text
    profile.data_json = json.dumps(data)
    if resume_path is not None:
        profile.resume_path = str(resume_path)
        profile.resume_filename = filename
    db.commit()
    return {"exists": True, "profile": profile.to_dict()}


class ProfileUpdate(BaseModel):
    full_name: str | None = None
    email: str | None = None
    phone: str | None = None
    location: str | None = None
    linkedin_url: str | None = None
    portfolio_url: str | None = None
    salary_expectation: str | None = None
    work_authorization: str | None = None
    availability: str | None = None
    demographics: dict | None = None


@router.put("")
def update_profile(update: ProfileUpdate, db: Session = Depends(get_db)):
    profile = db.get(Profile, 1)
    if profile is None:
        raise HTTPException(404, "Upload a resume first.")
    payload = update.model_dump(exclude_unset=True)
    demographics = payload.pop("demographics", None)
    for key, value in payload.items():
        setattr(profile, key, value)
    if demographics is not None:
        profile.demographics_json = json.dumps(demographics) if demographics else None
    db.commit()
    return {"exists": True, "profile": profile.to_dict()}
