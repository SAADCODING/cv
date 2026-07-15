import asyncio

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..db import SessionLocal
from ..models import Profile, Scan
from ..services import scan_runner

router = APIRouter(prefix="/api/scans", tags=["scans"])

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


class ScanRequest(BaseModel):
    urls: list[str]


@router.post("")
async def create_scans(request: ScanRequest, db: Session = Depends(get_db)):
    """Start a scan for each career page URL. Scans run in the background."""
    profile = db.get(Profile, 1)
    if profile is None or not profile.data_json:
        raise HTTPException(400, "Upload and parse a resume before scanning career pages.")

    urls = [u.strip() for u in request.urls if u.strip()]
    if not urls:
        raise HTTPException(400, "Provide at least one career page URL.")
    if len(urls) > 10:
        raise HTTPException(400, "At most 10 career page URLs per request.")

    scans = []
    for url in urls:
        if not url.startswith(("http://", "https://")):
            url = "https://" + url
        scan = Scan(url=url, status="pending")
        db.add(scan)
        db.commit()
        _spawn(scan_runner.run_scan(scan.id))
        scans.append(scan.to_dict())
    return {"scans": scans}


@router.get("")
def list_scans(db: Session = Depends(get_db)):
    scans = db.query(Scan).order_by(Scan.id.desc()).limit(50).all()
    return {"scans": [s.to_dict() for s in scans]}


@router.get("/{scan_id}")
def get_scan(scan_id: int, db: Session = Depends(get_db)):
    scan = db.get(Scan, scan_id)
    if scan is None:
        raise HTTPException(404, "Scan not found")
    return scan.to_dict()
