"""Shared Playwright browser lifecycle (used by the scanner and the autofiller)."""

import asyncio
import os

from playwright.async_api import Browser, Playwright, async_playwright

from ..config import HEADLESS, USER_AGENT

# Optional: point at a specific Chromium binary instead of the Playwright-managed one.
CHROMIUM_PATH = os.getenv("PLAYWRIGHT_CHROMIUM_PATH") or None

_playwright: Playwright | None = None
_browser: Browser | None = None
_lock = asyncio.Lock()


async def get_browser() -> Browser:
    global _playwright, _browser
    async with _lock:
        if _browser is None or not _browser.is_connected():
            if _playwright is None:
                _playwright = await async_playwright().start()
            _browser = await _playwright.chromium.launch(
                headless=HEADLESS, executable_path=CHROMIUM_PATH
            )
    return _browser


async def render_page_html(url: str, timeout_ms: int = 30000) -> str:
    """Load a URL in a fresh context (for JS-rendered pages) and return the HTML."""
    browser = await get_browser()
    context = await browser.new_context(user_agent=USER_AGENT)
    try:
        page = await context.new_page()
        await page.goto(url, timeout=timeout_ms, wait_until="domcontentloaded")
        try:
            await page.wait_for_load_state("networkidle", timeout=8000)
        except Exception:
            pass  # busy pages never go idle; use whatever has rendered
        return await page.content()
    finally:
        await context.close()


async def shutdown() -> None:
    global _playwright, _browser
    if _browser is not None:
        try:
            await _browser.close()
        except Exception:
            pass
        _browser = None
    if _playwright is not None:
        try:
            await _playwright.stop()
        except Exception:
            pass
        _playwright = None
