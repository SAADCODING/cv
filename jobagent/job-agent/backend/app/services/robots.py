"""robots.txt compliance check."""

import urllib.robotparser
from urllib.parse import urlsplit

import httpx

from ..config import USER_AGENT


async def robots_allowed(url: str) -> tuple[bool, str]:
    """Return (allowed, note). Unreachable/missing robots.txt counts as allowed."""
    parts = urlsplit(url)
    robots_url = f"{parts.scheme}://{parts.netloc}/robots.txt"
    try:
        async with httpx.AsyncClient(
            timeout=10, follow_redirects=True, headers={"User-Agent": USER_AGENT}
        ) as client:
            resp = await client.get(robots_url)
    except httpx.HTTPError:
        return True, "robots.txt unreachable; proceeding"
    if resp.status_code >= 400:
        return True, "no robots.txt"
    parser = urllib.robotparser.RobotFileParser()
    parser.parse(resp.text.splitlines())
    if parser.can_fetch(USER_AGENT, url) and parser.can_fetch("*", url):
        return True, "allowed by robots.txt"
    return False, (
        "This page is disallowed by the site's robots.txt, so the agent will not scan it. "
        "Please open the posting yourself and paste the job description manually."
    )
