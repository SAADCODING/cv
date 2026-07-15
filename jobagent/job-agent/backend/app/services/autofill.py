"""Playwright-based application form autofill.

Flow per application:
1. Open the job page in a fresh browser context and click through to the form.
2. Stop immediately if a CAPTCHA / login wall is detected (the user must do that part).
3. Enumerate visible form fields, tag them with data-agent-id attributes.
4. Ask the LLM to map candidate profile -> fields (skipping demographics/sensitive data).
5. Fill the form, attach the resume file, screenshot it, and mark ready_for_review.
6. NEVER click submit here. Submission happens only in confirm_submit(), which the
   API calls after the user's explicit confirmation.

The browser page stays open between fill and confirm so the review is of the real,
live form. If the server restarts in between, the user just re-runs the fill.
"""

import asyncio
import json
import logging
import re

from playwright.async_api import BrowserContext, Page

from .. import llm, prompts
from ..config import BLOCKED_DOMAINS, SCREENSHOT_DIR, USER_AGENT
from ..db import SessionLocal
from ..models import Application, Job, Profile
from . import browser

log = logging.getLogger("autofill")

# application_id -> {"context": BrowserContext, "page": Page}
SESSIONS: dict[int, dict] = {}

_COLLECT_FIELDS_JS = """
() => {
  const els = Array.from(document.querySelectorAll('input, select, textarea'));
  const results = [];
  let i = 0;
  for (const el of els) {
    const tag = el.tagName.toLowerCase();
    const type = (el.type || '').toLowerCase();
    if (['hidden', 'submit', 'button', 'image', 'reset'].includes(type)) continue;
    const visible = !!el.offsetParent || type === 'file';
    if (!visible) continue;
    const id = 'agent-f' + (i++);
    el.setAttribute('data-agent-id', id);
    let label = '';
    if (el.id) {
      try {
        const lab = document.querySelector('label[for="' + CSS.escape(el.id) + '"]');
        if (lab) label = lab.innerText;
      } catch (e) {}
    }
    if (!label) { const lab = el.closest('label'); if (lab) label = lab.innerText; }
    if (!label) label = el.getAttribute('aria-label') || '';
    if (!label) {
      const cont = el.closest('div,fieldset,li,section');
      if (cont) {
        const lab = cont.querySelector('label, legend');
        if (lab) label = lab.innerText;
      }
    }
    label = (label || '').replace(/\\s+/g, ' ').trim().slice(0, 300);
    const options = tag === 'select'
      ? Array.from(el.options).map(o => (o.label || o.value || '').trim()).filter(Boolean).slice(0, 80)
      : [];
    let value = '';
    if (tag === 'select') value = (el.selectedOptions[0] && el.selectedOptions[0].label) || '';
    else if (type === 'checkbox' || type === 'radio') value = el.checked ? 'checked' : '';
    else value = el.value || '';
    results.push({
      field_id: id,
      tag: tag,
      type: type || (tag === 'textarea' ? 'textarea' : 'text'),
      name: el.name || '',
      label: label,
      placeholder: el.getAttribute('placeholder') || '',
      required: !!el.required || el.getAttribute('aria-required') === 'true',
      current_value: String(value).slice(0, 200),
      options: options,
      radio_value: type === 'radio' ? (el.value || '') : ''
    });
  }
  return results;
}
"""

_BLOCKER_JS = """
() => {
  const blockers = [];
  if (document.querySelector('iframe[src*="recaptcha"], .g-recaptcha, iframe[src*="hcaptcha"], .h-captcha, iframe[src*="turnstile"], .cf-turnstile'))
    blockers.push('captcha');
  const pw = Array.from(document.querySelectorAll('input[type="password"]')).some(el => !!el.offsetParent);
  if (pw) blockers.push('login');
  return blockers;
}
"""


def _check_blocked_domain(url: str) -> str | None:
    for blocked in BLOCKED_DOMAINS:
        if blocked in url:
            return "This agent does not automate LinkedIn. Apply on the company site instead."
    return None


async def _click_apply_button(context: BrowserContext, page: Page) -> Page:
    """If the job page has an Apply button/link, click it. Returns the active page
    (a new tab if one opened)."""
    patterns = [re.compile(r"^apply", re.I), re.compile(r"apply (now|for|to)", re.I)]
    for role in ("link", "button"):
        for pattern in patterns:
            locator = page.get_by_role(role, name=pattern).first
            try:
                if not await locator.is_visible(timeout=1500):
                    continue
            except Exception:
                continue
            pages_before = len(context.pages)
            try:
                await locator.click(timeout=5000)
            except Exception:
                continue
            await asyncio.sleep(2.5)
            if len(context.pages) > pages_before:
                new_page = context.pages[-1]
                try:
                    await new_page.wait_for_load_state("domcontentloaded", timeout=15000)
                except Exception:
                    pass
                return new_page
            try:
                await page.wait_for_load_state("domcontentloaded", timeout=15000)
            except Exception:
                pass
            return page
    return page


async def _screenshot(page: Page, application_id: int) -> str:
    path = SCREENSHOT_DIR / f"application_{application_id}.png"
    try:
        await page.screenshot(path=str(path), full_page=True)
    except Exception:
        try:
            await page.screenshot(path=str(path))
        except Exception:
            return ""
    return str(path)


def _build_field_map_input(profile: Profile, job: Job, fields: list[dict]) -> str:
    extras = {
        "linkedin_url": profile.linkedin_url,
        "portfolio_url": profile.portfolio_url,
        "salary_expectation": profile.salary_expectation,
        "work_authorization": profile.work_authorization,
        "availability": profile.availability,
        "saved_demographic_preferences": profile.demographics or "none saved - skip all demographic questions",
    }
    return (
        "CANDIDATE PROFILE:\n" + json.dumps(profile.data, indent=1)
        + "\n\nCANDIDATE EXTRAS:\n" + json.dumps(extras, indent=1)
        + "\n\nJOB:\n" + json.dumps(
            {
                "company": job.company,
                "title": job.title,
                "description_excerpt": (job.description or "")[:6000],
            },
            indent=1,
        )
        + "\n\nFORM FIELDS:\n" + json.dumps(fields, indent=1)
    )


async def _apply_actions(page: Page, actions: list[dict], fields_by_id: dict[str, dict],
                         resume_path: str | None) -> list[dict]:
    """Execute the LLM's field actions. Returns a review-friendly list of results."""
    review: list[dict] = []
    for action in actions:
        field_id = action.get("field_id")
        meta = fields_by_id.get(field_id)
        if meta is None:
            continue
        kind = action.get("action")
        value = action.get("value")
        selector = f'[data-agent-id="{field_id}"]'
        status = "skipped"
        try:
            if kind == "fill" and value is not None:
                await page.fill(selector, str(value), timeout=5000)
                status = "filled"
            elif kind == "select" and value is not None:
                try:
                    await page.select_option(selector, label=str(value), timeout=5000)
                except Exception:
                    await page.select_option(selector, value=str(value), timeout=5000)
                status = "filled"
            elif kind == "check":
                await page.check(selector, timeout=5000)
                status = "filled"
            elif kind == "upload_resume" and resume_path:
                await page.set_input_files(selector, resume_path, timeout=8000)
                status = "filled"
        except Exception as e:
            status = "error"
            log.warning("field %s (%s): %s", field_id, meta.get("label"), e)
        review.append(
            {
                "field_id": field_id,
                "label": meta.get("label") or meta.get("placeholder") or meta.get("name") or field_id,
                "kind": meta.get("tag"),
                "type": meta.get("type"),
                "action": kind,
                "value": "(resume file)" if kind == "upload_resume" else value,
                "reason": action.get("reason"),
                "status": status,
            }
        )
    return review


async def run_fill(application_id: int) -> None:
    """Background task: open the application page and fill it. Never submits."""
    db = SessionLocal()
    try:
        application = db.get(Application, application_id)
        if application is None:
            return
        job = db.get(Job, application.job_id)
        profile = db.get(Profile, 1)
        if job is None or profile is None:
            application.status = "failed"
            application.message = "Missing job or profile."
            db.commit()
            return

        blocked = _check_blocked_domain(job.url)
        if blocked:
            application.status = "failed"
            application.message = blocked
            db.commit()
            return

        chromium = await browser.get_browser()
        context = await chromium.new_context(user_agent=USER_AGENT)
        page = await context.new_page()
        SESSIONS[application_id] = {"context": context, "page": page}

        try:
            await page.goto(job.url, timeout=45000, wait_until="domcontentloaded")
            try:
                await page.wait_for_load_state("networkidle", timeout=8000)
            except Exception:
                pass

            page = await _click_apply_button(context, page)
            SESSIONS[application_id]["page"] = page
            try:
                await page.wait_for_load_state("networkidle", timeout=8000)
            except Exception:
                pass

            blockers = await page.evaluate(_BLOCKER_JS)
            if blockers:
                what = " and ".join(sorted(set(blockers)))
                application.status = "needs_user_action"
                application.message = (
                    f"This application requires a {what} step, which the agent will not "
                    "automate. Please open the job page in your own browser and complete "
                    "the application manually (your generated answers are still available "
                    "on the job page)."
                )
                application.screenshot_path = await _screenshot(page, application_id)
                db.commit()
                return

            fields = await page.evaluate(_COLLECT_FIELDS_JS)
            if not fields:
                application.status = "needs_user_action"
                application.message = (
                    "No form fields were found on this page. The application may use a "
                    "non-standard widget or open elsewhere - please apply manually."
                )
                application.screenshot_path = await _screenshot(page, application_id)
                db.commit()
                return

            mapping = await asyncio.to_thread(
                llm.structured,
                prompts.FIELD_MAP_SYSTEM,
                _build_field_map_input(profile, job, fields),
                prompts.FIELD_MAP_SCHEMA,
                16000,
            )
            fields_by_id = {f["field_id"]: f for f in fields}
            review = await _apply_actions(
                page, mapping.get("fields", []), fields_by_id, profile.resume_path
            )

            answers = [
                {"question": r["label"], "answer": r["value"]}
                for r in review
                if r["type"] == "textarea" and r["action"] == "fill" and r["status"] == "filled"
            ]

            application.fields_json = json.dumps(review)
            application.answers_json = json.dumps(answers)
            application.screenshot_path = await _screenshot(page, application_id)
            application.status = "ready_for_review"
            application.message = (
                "The form has been filled. Review everything carefully before submitting. "
                "Nothing has been sent to the employer yet."
            )
            db.commit()
        except Exception as e:
            log.exception("autofill failed")
            application.status = "failed"
            application.message = f"Autofill failed: {e}"
            try:
                application.screenshot_path = await _screenshot(page, application_id)
            except Exception:
                pass
            db.commit()
    finally:
        db.close()


async def update_field(application_id: int, field_id: str, value: str) -> dict:
    """Apply a user edit to the live form. Returns the updated application dict."""
    session = SESSIONS.get(application_id)
    db = SessionLocal()
    try:
        application = db.get(Application, application_id)
        if application is None:
            raise ValueError("Application not found")
        if session is None:
            raise ValueError(
                "The browser session for this application is no longer open. "
                "Re-run Apply to fill the form again."
            )
        page: Page = session["page"]
        selector = f'[data-agent-id="{field_id}"]'
        fields = json.loads(application.fields_json or "[]")
        target = next((f for f in fields if f["field_id"] == field_id), None)
        if target is None:
            raise ValueError("Unknown field")
        if target["kind"] == "select":
            try:
                await page.select_option(selector, label=value, timeout=5000)
            except Exception:
                await page.select_option(selector, value=value, timeout=5000)
        else:
            await page.fill(selector, value, timeout=5000)
        target["value"] = value
        target["status"] = "filled"
        target["action"] = target["action"] if target["action"] != "skip" else "fill"
        application.fields_json = json.dumps(fields)
        application.answers_json = json.dumps(
            [
                {"question": f["label"], "answer": f["value"]}
                for f in fields
                if f["type"] == "textarea" and f["status"] == "filled"
            ]
        )
        application.screenshot_path = await _screenshot(page, application_id)
        db.commit()
        return application.to_dict()
    finally:
        db.close()


async def confirm_submit(application_id: int) -> dict:
    """Click the real submit button. Only called after explicit user confirmation."""
    session = SESSIONS.get(application_id)
    db = SessionLocal()
    try:
        application = db.get(Application, application_id)
        if application is None:
            raise ValueError("Application not found")
        if application.status != "ready_for_review":
            raise ValueError(f"Application is not ready to submit (status: {application.status}).")
        if session is None:
            raise ValueError(
                "The browser session for this application is no longer open. "
                "Re-run Apply to fill the form again, then confirm."
            )
        page: Page = session["page"]

        submit = None
        for locator in (
            page.locator('button[type="submit"]').first,
            page.locator('input[type="submit"]').first,
            page.get_by_role("button", name=re.compile(r"submit", re.I)).first,
            page.get_by_role("button", name=re.compile(r"^(send|apply)\b", re.I)).first,
        ):
            try:
                if await locator.is_visible(timeout=1500):
                    submit = locator
                    break
            except Exception:
                continue
        if submit is None:
            application.status = "needs_user_action"
            application.message = "No submit button was found; please submit manually."
            db.commit()
            return application.to_dict()

        await submit.click(timeout=10000)
        try:
            await page.wait_for_load_state("networkidle", timeout=15000)
        except Exception:
            await asyncio.sleep(3)

        application.screenshot_path = await _screenshot(page, application_id)
        application.status = "submitted"
        application.message = "Submit was clicked. Check the confirmation screenshot / your email."
        db.commit()

        await close_session(application_id)
        return application.to_dict()
    finally:
        db.close()


async def close_session(application_id: int) -> None:
    session = SESSIONS.pop(application_id, None)
    if session is not None:
        try:
            await session["context"].close()
        except Exception:
            pass
