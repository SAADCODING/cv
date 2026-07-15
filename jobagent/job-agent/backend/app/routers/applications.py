import asyncio

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..db import SessionLocal
from ..models import Application, Job, Profile
from ..services import autofill

router = APIRouter(prefix="/api", tags=["applications"])

# Keep strong references so background tasks aren't garbage-collected mid-run.
_tasks: set[asyncio.Task] = set()


def _spawn(coro) -> None:
    task = asyncio.create_task(coro)
    _tasks.add(task)
    task.add_done_callback(_tasks.discard)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.post("/jobs/{job_id}/apply")
async def start_application(job_id: int, db: Session = Depends(get_db)):
    """Open the application page and start filling it (never submits)."""
    job = db.get(Job, job_id)
    if job is None:
        raise HTTPException(404, "Job not found")
    profile = db.get(Profile, 1)
    if profile is None or not profile.data_json:
        raise HTTPException(400, "Upload a resume first.")
    if job.fit_category not in ("strong", "good"):
        raise HTTPException(
            400,
            "Autofill is only offered for strong or good fits. This job is rated "
            f"'{job.fit_category or 'unscored'}' - applying to poor fits is discouraged.",
        )

    application = Application(job_id=job_id, status="filling",
                              message="Opening the application page and filling the form...")
    db.add(application)
    db.commit()
    _spawn(autofill.run_fill(application.id))
    return application.to_dict()


@router.get("/applications")
def list_applications(db: Session = Depends(get_db)):
    apps = db.query(Application).order_by(Application.id.desc()).limit(100).all()
    return {"applications": [a.to_dict() for a in apps]}


@router.get("/applications/{application_id}")
def get_application(application_id: int, db: Session = Depends(get_db)):
    application = db.get(Application, application_id)
    if application is None:
        raise HTTPException(404, "Application not found")
    return application.to_dict()


@router.get("/applications/{application_id}/screenshot")
def get_screenshot(application_id: int, db: Session = Depends(get_db)):
    application = db.get(Application, application_id)
    if application is None or not application.screenshot_path:
        raise HTTPException(404, "No screenshot available")
    return FileResponse(application.screenshot_path, media_type="image/png")


class FieldUpdate(BaseModel):
    field_id: str
    value: str


@router.patch("/applications/{application_id}/fields")
async def edit_field(application_id: int, update: FieldUpdate):
    """Edit one field on the live (still-open) application form."""
    try:
        return await autofill.update_field(application_id, update.field_id, update.value)
    except ValueError as e:
        raise HTTPException(400, str(e))


class ConfirmRequest(BaseModel):
    confirm: bool


@router.post("/applications/{application_id}/confirm")
async def confirm_submission(application_id: int, request: ConfirmRequest):
    """Submit the application. Requires explicit confirmation from the user."""
    if not request.confirm:
        raise HTTPException(400, "Submission requires explicit confirmation (confirm: true).")
    try:
        return await autofill.confirm_submit(application_id)
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.post("/applications/{application_id}/cancel")
async def cancel_application(application_id: int, db: Session = Depends(get_db)):
    application = db.get(Application, application_id)
    if application is None:
        raise HTTPException(404, "Application not found")
    await autofill.close_session(application_id)
    if application.status not in ("submitted",):
        application.status = "cancelled"
        application.message = "Cancelled by the user. Nothing was submitted."
        db.commit()
    return application.to_dict()
