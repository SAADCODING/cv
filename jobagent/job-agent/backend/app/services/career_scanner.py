"""Scan a company careers page and return job postings.

Strategy:
1. Refuse blocked domains (LinkedIn) and robots.txt-disallowed pages.
2. If the URL belongs to a known ATS (Greenhouse, Lever, Ashby, Workable), use the
   ATS's public job-board API - fast, reliable, and usually includes descriptions.
3. Otherwise fetch the page (Playwright fallback for JS-rendered sites), collect
   links, and let the LLM pick out the individual job-posting links.
"""

import asyncio
import html as html_lib
import json
import re
from dataclasses import dataclass, field
from urllib.parse import urljoin, urlsplit

import httpx
from bs4 import BeautifulSoup

from .. import llm, prompts
from ..config import BLOCKED_DOMAINS, FETCH_DELAY_SECONDS, MAX_JOBS_PER_SCAN, USER_AGENT
from . import browser, robots


class ScanError(Exception):
    """User-facing scan failure."""


@dataclass
class JobPosting:
    url: str
    title: str = ""
    company: str = ""
    location: str = ""
    employment_type: str = ""
    description_text: str = ""  # filled from ATS APIs; empty means fetch the page
    source: str = "generic"
    extra: dict = field(default_factory=dict)


def _domain(url: str) -> str:
    return urlsplit(url).netloc.lower()


def _check_blocked(url: str) -> None:
    dom = _domain(url)
    for blocked in BLOCKED_DOMAINS:
        if dom == blocked or dom.endswith("." + blocked):
            raise ScanError(
                "This agent does not scan LinkedIn (or automate LinkedIn Easy Apply). "
                "Please use the company's own careers page instead."
            )


async def _get_json(url: str) -> dict | list:
    async with httpx.AsyncClient(
        timeout=30, follow_redirects=True, headers={"User-Agent": USER_AGENT}
    ) as client:
        resp = await client.get(url)
        resp.raise_for_status()
        return resp.json()


async def _get_html(url: str) -> str:
    async with httpx.AsyncClient(
        timeout=30, follow_redirects=True, headers={"User-Agent": USER_AGENT}
    ) as client:
        resp = await client.get(url)
        resp.raise_for_status()
        return resp.text


def html_to_text(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "noscript", "template"]):
        tag.decompose()
    text = soup.get_text(separator="\n")
    lines = [line.strip() for line in text.splitlines()]
    return "\n".join(line for line in lines if line)


# --------------------------------------------------------------------------
# ATS adapters
# --------------------------------------------------------------------------

async def _scan_greenhouse(token: str) -> list[JobPosting]:
    data = await _get_json(
        f"https://boards-api.greenhouse.io/v1/boards/{token}/jobs?content=true"
    )
    postings = []
    for job in data.get("jobs", []):
        content = html_lib.unescape(job.get("content") or "")
        postings.append(
            JobPosting(
                url=job.get("absolute_url") or "",
                title=job.get("title") or "",
                company=(data.get("meta") or {}).get("name") or token,
                location=((job.get("location") or {}).get("name")) or "",
                description_text=html_to_text(content),
                source="greenhouse",
            )
        )
    return [p for p in postings if p.url]


async def _scan_lever(company: str, eu: bool = False) -> list[JobPosting]:
    api_host = "api.eu.lever.co" if eu else "api.lever.co"
    data = await _get_json(f"https://{api_host}/v0/postings/{company}?mode=json")
    postings = []
    for job in data if isinstance(data, list) else []:
        parts = [job.get("descriptionPlain") or ""]
        for lst in job.get("lists") or []:
            parts.append(lst.get("text") or "")
            parts.append(html_to_text(lst.get("content") or ""))
        parts.append(job.get("additionalPlain") or "")
        categories = job.get("categories") or {}
        postings.append(
            JobPosting(
                url=job.get("hostedUrl") or "",
                title=job.get("text") or "",
                company=company,
                location=categories.get("location") or "",
                employment_type=categories.get("commitment") or "",
                description_text="\n".join(p for p in parts if p).strip(),
                source="lever",
            )
        )
    return [p for p in postings if p.url]


async def _scan_ashby(org: str) -> list[JobPosting]:
    data = await _get_json(
        f"https://api.ashbyhq.com/posting-api/job-board/{org}?includeCompensation=true"
    )
    postings = []
    for job in data.get("jobs", []):
        if job.get("isListed") is False:
            continue
        postings.append(
            JobPosting(
                url=job.get("jobUrl") or job.get("applyUrl") or "",
                title=job.get("title") or "",
                company=org,
                location=job.get("location") or "",
                employment_type=job.get("employmentType") or "",
                description_text=html_to_text(job.get("descriptionHtml") or ""),
                source="ashby",
            )
        )
    return [p for p in postings if p.url]


async def _scan_workable(account: str) -> list[JobPosting]:
    data = await _get_json(
        f"https://apply.workable.com/api/v1/widget/accounts/{account}?details=true"
    )
    postings = []
    company = data.get("name") or account
    for job in data.get("jobs", []):
        location_bits = [job.get("city") or "", job.get("country") or ""]
        postings.append(
            JobPosting(
                url=job.get("url") or job.get("shortlink") or "",
                title=job.get("title") or "",
                company=company,
                location=", ".join(b for b in location_bits if b),
                employment_type=job.get("employment_type") or "",
                description_text=html_to_text(job.get("description") or ""),
                source="workable",
            )
        )
    return [p for p in postings if p.url]


_ATS_PATTERNS: list[tuple[re.Pattern, str]] = [
    (re.compile(r"(?:job-)?boards\.greenhouse\.io/(?:embed/job_board\?for=)?([A-Za-z0-9_-]+)"), "greenhouse"),
    (re.compile(r"jobs\.(eu\.)?lever\.co/([A-Za-z0-9_-]+)"), "lever"),
    (re.compile(r"jobs\.ashbyhq\.com/([A-Za-z0-9_-]+)"), "ashby"),
    (re.compile(r"apply\.workable\.com/([A-Za-z0-9_-]+)"), "workable"),
]


async def _try_ats(url: str) -> list[JobPosting] | None:
    for pattern, kind in _ATS_PATTERNS:
        match = pattern.search(url)
        if not match:
            continue
        try:
            if kind == "greenhouse":
                return await _scan_greenhouse(match.group(1))
            if kind == "lever":
                return await _scan_lever(match.group(2), eu=bool(match.group(1)))
            if kind == "ashby":
                return await _scan_ashby(match.group(1))
            if kind == "workable":
                return await _scan_workable(match.group(1))
        except (httpx.HTTPError, json.JSONDecodeError, KeyError):
            return None  # fall back to the generic scanner
    return None


# --------------------------------------------------------------------------
# Generic scanner
# --------------------------------------------------------------------------

def _collect_links(page_html: str, base_url: str) -> list[dict]:
    soup = BeautifulSoup(page_html, "html.parser")
    base_domain = _domain(base_url)
    known_ats = ("greenhouse.io", "lever.co", "ashbyhq.com", "workable.com",
                 "myworkdayjobs.com", "smartrecruiters.com", "icims.com",
                 "bamboohr.com", "jobvite.com", "recruitee.com", "breezy.hr")
    seen: set[str] = set()
    links: list[dict] = []
    for anchor in soup.find_all("a", href=True):
        href = urljoin(base_url, anchor["href"].strip())
        if not href.startswith(("http://", "https://")):
            continue
        href = href.split("#", 1)[0]
        if not href or href in seen:
            continue
        dom = _domain(href)
        if any(dom == b or dom.endswith("." + b) for b in BLOCKED_DOMAINS):
            continue
        same_site = dom == base_domain or dom.endswith("." + base_domain.split(".", 1)[-1])
        ats_link = any(dom.endswith(a) for a in known_ats)
        if not (same_site or ats_link):
            continue
        text = " ".join(anchor.get_text(separator=" ").split())[:120]
        seen.add(href)
        links.append({"url": href, "text": text})
        if len(links) >= 400:
            break
    return links


async def _scan_generic(url: str) -> list[JobPosting]:
    try:
        page_html = await _get_html(url)
    except httpx.HTTPError:
        page_html = ""
    links = _collect_links(page_html, url) if page_html else []
    if len(links) < 5:
        # Probably JS-rendered - retry with a real browser.
        try:
            page_html = await browser.render_page_html(url)
            links = _collect_links(page_html, url)
        except Exception as e:
            if not links:
                raise ScanError(
                    f"Could not load this careers page ({e}). If the site blocks "
                    "automated access, paste the job description manually instead."
                ) from e
    if not links:
        raise ScanError(
            "No links were found on this page. If the postings are behind a search "
            "widget or login, open a specific job posting URL and scan that instead."
        )
    job_links = await asyncio.to_thread(_select_job_links_sync, url, links)
    if not job_links:
        raise ScanError(
            "No individual job postings were identified on this page. Try a more "
            "specific careers/jobs URL, or paste a job description manually."
        )
    company_guess = _domain(url).split(".")[-2].capitalize() if "." in _domain(url) else ""
    return [
        JobPosting(url=jl["url"], title=jl.get("title") or "", company=company_guess)
        for jl in job_links
    ]


def _select_job_links_sync(page_url: str, links: list[dict]) -> list[dict]:
    system = prompts.LINK_SELECT_SYSTEM.format(max_jobs=MAX_JOBS_PER_SCAN)
    user = (
        f"Careers page: {page_url}\n\nLinks found on the page (url | anchor text):\n"
        + "\n".join(f"{l['url']} | {l['text']}" for l in links)
    )
    result = llm.structured(system, user, prompts.LINK_SELECT_SCHEMA, max_tokens=8192)
    return result.get("job_links", [])[:MAX_JOBS_PER_SCAN]


# --------------------------------------------------------------------------
# Job page fetch (for postings without a description yet)
# --------------------------------------------------------------------------

async def fetch_job_description(url: str) -> str:
    _check_blocked(url)
    text = ""
    try:
        page_html = await _get_html(url)
        text = html_to_text(page_html)
    except httpx.HTTPError:
        pass
    if len(text) < 400:  # JS-rendered or blocked; try a real browser
        try:
            page_html = await browser.render_page_html(url)
            text = html_to_text(page_html)
        except Exception:
            pass
    return text


# --------------------------------------------------------------------------
# Entry point
# --------------------------------------------------------------------------

async def scan_career_page(url: str) -> list[JobPosting]:
    _check_blocked(url)
    allowed, note = await robots.robots_allowed(url)
    if not allowed:
        raise ScanError(note)

    postings = await _try_ats(url)
    if postings is None:
        postings = await _scan_generic(url)
    if not postings:
        raise ScanError("No open job postings were found on this page.")

    # Politeness + cost cap
    await asyncio.sleep(FETCH_DELAY_SECONDS)
    return postings[:MAX_JOBS_PER_SCAN]
