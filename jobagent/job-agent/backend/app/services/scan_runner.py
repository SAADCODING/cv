"""Background orchestration of a career-page scan:
find postings -> fetch descriptions -> extract + score each job -> save incrementally.
"""

import asyncio
import json
import logging

from ..config import FETCH_DELAY_SECONDS
from ..db import SessionLocal
from ..llm import LLMError
from ..models import Job, Profile, Scan
from . import career_scanner, matcher
from .career_scanner import ScanError

log = logging.getLogger("scan")


async def run_scan(scan_id: int) -> None:
    db = SessionLocal()
    try:
        scan = db.get(Scan, scan_id)
        profile = db.get(Profile, 1)
        if scan is None:
            return
        if profile is None or not profile.data_json:
            scan.status = "failed"
            scan.message = "Upload and parse a resume before scanning."
            db.commit()
            return

        scan.status = "running"
        db.commit()

        try:
            postings = await career_scanner.scan_career_page(scan.url)
        except ScanError as e:
            scan.status = "failed"
            scan.message = str(e)
            db.commit()
            return
        except LLMError as e:
            scan.status = "failed"
            scan.message = str(e)
            db.commit()
            return
        except Exception as e:  # unexpected
            log.exception("scan failed")
            scan.status = "failed"
            scan.message = f"Unexpected error while scanning: {e}"
            db.commit()
            return

        scan.jobs_found = len(postings)
        db.commit()

        profile_data = profile.data
        errors = 0
        for posting in postings:
            try:
                description = posting.description_text
                if len(description) < 200:
                    description = await career_scanner.fetch_job_description(posting.url)
                    await asyncio.sleep(FETCH_DELAY_SECONDS)
                if len(description) < 200:
                    raise ScanError("Could not read the job description from this page.")

                meta = {
                    "listed_title": posting.title,
                    "listed_company": posting.company,
                    "listed_location": posting.location,
                    "listed_employment_type": posting.employment_type,
                    "url": posting.url,
                }
                result = await asyncio.to_thread(matcher.match_job, profile_data, meta, description)

                job = Job(
                    scan_id=scan.id,
                    company=result.get("company") or posting.company or None,
                    title=result.get("title") or posting.title or None,
                    location=result.get("location") or posting.location or None,
                    work_mode=result.get("work_mode") or "unspecified",
                    employment_type=result.get("employment_type") or posting.employment_type or None,
                    url=posting.url,
                    description=description[:100000],
                    details_json=json.dumps(
                        {
                            "required_qualifications": result.get("required_qualifications", []),
                            "preferred_qualifications": result.get("preferred_qualifications", []),
                            "required_skills": result.get("required_skills", []),
                            "preferred_skills": result.get("preferred_skills", []),
                            "years_experience_required": result.get("years_experience_required"),
                            "education_requirements": result.get("education_requirements"),
                            "application_questions": result.get("application_questions", []),
                        }
                    ),
                    fit_score=result.get("fit_score"),
                    fit_category=result.get("fit_category"),
                    matching_skills_json=json.dumps(result.get("matching_skills", [])),
                    missing_skills_json=json.dumps(result.get("missing_skills", [])),
                    why_match=result.get("why_match"),
                    why_not_match=result.get("why_not_match"),
                    recommendation=result.get("recommendation"),
                )
                db.add(job)
            except Exception as e:
                errors += 1
                log.warning("failed to process %s: %s", posting.url, e)
            finally:
                scan.jobs_processed += 1
                db.commit()

        scan.status = "completed"
        if errors:
            scan.message = f"Done, but {errors} of {scan.jobs_found} postings could not be processed."
        db.commit()
    finally:
        db.close()
