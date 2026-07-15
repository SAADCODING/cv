import json

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..db import SessionLocal
from ..llm import LLMError
from ..models import Job, Profile
from ..services import answers as answers_service

router = APIRouter(prefix="/api/jobs", tags=["jobs"])


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.get("")
def list_jobs(
    scan_id: int | None = None,
    min_score: float | None = None,
    category: str | None = None,
    db: Session = Depends(get_db),
):
    query = db.query(Job)
    if scan_id is not None:
        query = query.filter(Job.scan_id == scan_id)
    if min_score is not None:
        query = query.filter(Job.fit_score >= min_score)
    if category:
        query = query.filter(Job.fit_category == category)
    jobs = query.order_by(Job.fit_score.desc()).limit(500).all()
    return {"jobs": [j.to_dict() for j in jobs]}


@router.get("/{job_id}")
def get_job(job_id: int, db: Session = Depends(get_db)):
    job = db.get(Job, job_id)
    if job is None:
        raise HTTPException(404, "Job not found")
    return job.to_dict(full=True)


class AnswersRequest(BaseModel):
    questions: list[str] | None = None


@router.post("/{job_id}/answers")
def generate_answers(job_id: int, request: AnswersRequest, db: Session = Depends(get_db)):
    """Generate tailored written answers for this job's application questions."""
    job = db.get(Job, job_id)
    if job is None:
        raise HTTPException(404, "Job not found")
    profile = db.get(Profile, 1)
    if profile is None or not profile.data_json:
        raise HTTPException(400, "Upload a resume first.")

    questions = request.questions or job.details.get("application_questions") or []
    if not questions:
        questions = [
            "Why are you interested in this role?",
            "Why are you a good fit for this position?",
        ]
    try:
        generated = answers_service.generate_answers(
            profile.data,
            {"company": job.company, "title": job.title, "description": job.description},
            questions,
        )
    except LLMError as e:
        raise HTTPException(502, str(e))

    details = job.details
    details["generated_answers"] = generated
    job.details_json = json.dumps(details)
    db.commit()
    return {"answers": generated}
