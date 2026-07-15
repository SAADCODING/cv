import json
from datetime import datetime, timezone

from sqlalchemy import Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from .db import Base


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class Profile(Base):
    """Single-user profile (row id is always 1 in the MVP)."""

    __tablename__ = "profiles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    full_name: Mapped[str | None] = mapped_column(String, nullable=True)
    email: Mapped[str | None] = mapped_column(String, nullable=True)
    phone: Mapped[str | None] = mapped_column(String, nullable=True)
    location: Mapped[str | None] = mapped_column(String, nullable=True)
    linkedin_url: Mapped[str | None] = mapped_column(String, nullable=True)
    portfolio_url: Mapped[str | None] = mapped_column(String, nullable=True)
    salary_expectation: Mapped[str | None] = mapped_column(String, nullable=True)
    work_authorization: Mapped[str | None] = mapped_column(String, nullable=True)
    availability: Mapped[str | None] = mapped_column(String, nullable=True)
    resume_filename: Mapped[str | None] = mapped_column(String, nullable=True)
    resume_path: Mapped[str | None] = mapped_column(String, nullable=True)
    resume_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    data_json: Mapped[str | None] = mapped_column(Text, nullable=True)  # full extracted profile
    demographics_json: Mapped[str | None] = mapped_column(Text, nullable=True)  # opt-in saved answers
    created_at: Mapped[str] = mapped_column(String, default=_now)
    updated_at: Mapped[str] = mapped_column(String, default=_now, onupdate=_now)

    @property
    def data(self) -> dict:
        return json.loads(self.data_json) if self.data_json else {}

    @property
    def demographics(self) -> dict:
        return json.loads(self.demographics_json) if self.demographics_json else {}

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "full_name": self.full_name,
            "email": self.email,
            "phone": self.phone,
            "location": self.location,
            "linkedin_url": self.linkedin_url,
            "portfolio_url": self.portfolio_url,
            "salary_expectation": self.salary_expectation,
            "work_authorization": self.work_authorization,
            "availability": self.availability,
            "resume_filename": self.resume_filename,
            "has_resume_file": bool(self.resume_path),
            "data": self.data,
            "demographics": self.demographics,
            "updated_at": self.updated_at,
        }


class Scan(Base):
    __tablename__ = "scans"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    url: Mapped[str] = mapped_column(String)
    status: Mapped[str] = mapped_column(String, default="pending")  # pending|running|completed|failed
    message: Mapped[str | None] = mapped_column(Text, nullable=True)
    jobs_found: Mapped[int] = mapped_column(Integer, default=0)
    jobs_processed: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[str] = mapped_column(String, default=_now)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "url": self.url,
            "status": self.status,
            "message": self.message,
            "jobs_found": self.jobs_found,
            "jobs_processed": self.jobs_processed,
            "created_at": self.created_at,
        }


class Job(Base):
    __tablename__ = "jobs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    scan_id: Mapped[int | None] = mapped_column(ForeignKey("scans.id"), nullable=True)
    company: Mapped[str | None] = mapped_column(String, nullable=True)
    title: Mapped[str | None] = mapped_column(String, nullable=True)
    location: Mapped[str | None] = mapped_column(String, nullable=True)
    work_mode: Mapped[str | None] = mapped_column(String, nullable=True)  # remote|hybrid|onsite|unspecified
    employment_type: Mapped[str | None] = mapped_column(String, nullable=True)
    url: Mapped[str] = mapped_column(String)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    details_json: Mapped[str | None] = mapped_column(Text, nullable=True)  # extracted quals/skills/questions
    fit_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    fit_category: Mapped[str | None] = mapped_column(String, nullable=True)  # strong|good|maybe|weak
    matching_skills_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    missing_skills_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    why_match: Mapped[str | None] = mapped_column(Text, nullable=True)
    why_not_match: Mapped[str | None] = mapped_column(Text, nullable=True)
    recommendation: Mapped[str | None] = mapped_column(String, nullable=True)  # apply|maybe|skip
    created_at: Mapped[str] = mapped_column(String, default=_now)

    @property
    def details(self) -> dict:
        return json.loads(self.details_json) if self.details_json else {}

    def to_dict(self, full: bool = False) -> dict:
        d = {
            "id": self.id,
            "scan_id": self.scan_id,
            "company": self.company,
            "title": self.title,
            "location": self.location,
            "work_mode": self.work_mode,
            "employment_type": self.employment_type,
            "url": self.url,
            "fit_score": self.fit_score,
            "fit_category": self.fit_category,
            "matching_skills": json.loads(self.matching_skills_json) if self.matching_skills_json else [],
            "missing_skills": json.loads(self.missing_skills_json) if self.missing_skills_json else [],
            "why_match": self.why_match,
            "why_not_match": self.why_not_match,
            "recommendation": self.recommendation,
            "created_at": self.created_at,
        }
        if full:
            d["description"] = self.description
            d["details"] = self.details
        return d


class Application(Base):
    __tablename__ = "applications"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    job_id: Mapped[int] = mapped_column(ForeignKey("jobs.id"))
    # filling | ready_for_review | needs_user_action | submitted | failed | cancelled
    status: Mapped[str] = mapped_column(String, default="filling")
    message: Mapped[str | None] = mapped_column(Text, nullable=True)
    fields_json: Mapped[str | None] = mapped_column(Text, nullable=True)  # filled form fields
    answers_json: Mapped[str | None] = mapped_column(Text, nullable=True)  # generated written answers
    screenshot_path: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[str] = mapped_column(String, default=_now)
    updated_at: Mapped[str] = mapped_column(String, default=_now, onupdate=_now)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "job_id": self.job_id,
            "status": self.status,
            "message": self.message,
            "fields": json.loads(self.fields_json) if self.fields_json else [],
            "answers": json.loads(self.answers_json) if self.answers_json else [],
            "has_screenshot": bool(self.screenshot_path),
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }
