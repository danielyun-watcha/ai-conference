"""Check whether a conference's accepted-papers page has gone live.

Heuristic: fetch the URL with an httpx GET. The page is considered "released"
when all of the following hold:
  - HTTP status is 200
  - Response body is non-trivially sized (avoids placeholder stubs)
  - The body contains at least one keyword associated with an accepted-papers
    listing AND does not look like a "coming soon" / 404 placeholder

This is intentionally conservative — a false negative just delays the Slack
notification by one poll cycle; a false positive would fire a wrong alert.
"""

import re
from dataclasses import dataclass
from typing import Optional

import httpx

from backend.config import HTTP_TIMEOUT, USER_AGENT

_POSITIVE_PATTERNS = [
    re.compile(r"accepted\s+papers?", re.IGNORECASE),
    re.compile(r"list\s+of\s+accepted", re.IGNORECASE),
    re.compile(r"paper\s+list", re.IGNORECASE),
    re.compile(r"\bproceedings\b", re.IGNORECASE),  # PMLR, IJCAI, AAAI OJS
    re.compile(r"\banthology\b", re.IGNORECASE),  # aclanthology
    re.compile(r"open\s*access", re.IGNORECASE),  # CVF openaccess
    re.compile(r"published\s+papers?", re.IGNORECASE),
]

_NEGATIVE_PATTERNS = [
    re.compile(r"coming\s+soon", re.IGNORECASE),
    re.compile(r"\bTBA\b"),
    re.compile(r"not\s+yet\s+available", re.IGNORECASE),
    re.compile(r"page\s+not\s+found", re.IGNORECASE),
    re.compile(r"\b404\s+not\s+found\b", re.IGNORECASE),
]

_MIN_BODY_CHARS = 1000
# Pages larger than this with no negative markers are trusted as real listings
# even without a positive phrase match — handles JS-light proceedings sites.
_LARGE_BODY_CHARS = 8000


@dataclass
class CheckResult:
    released: bool
    status_code: Optional[int]
    error: Optional[str]


def _looks_released(body: str) -> bool:
    if len(body) < _MIN_BODY_CHARS:
        return False
    # Negative phrases like "page not found" / "coming soon" only signal a
    # placeholder when they're the page's main message. SPA bundles often
    # embed them as i18n labels — apply the check only to small pages.
    if len(body) < 5000 and any(p.search(body) for p in _NEGATIVE_PATTERNS):
        return False
    if any(p.search(body) for p in _POSITIVE_PATTERNS):
        return True
    return len(body) >= _LARGE_BODY_CHARS


async def check_url(url: str, client: Optional[httpx.AsyncClient] = None) -> CheckResult:
    headers = {"User-Agent": USER_AGENT}
    owns_client = client is None
    if owns_client:
        client = httpx.AsyncClient(
            timeout=HTTP_TIMEOUT, follow_redirects=True, headers=headers
        )
    try:
        try:
            resp = await client.get(url, headers=headers)
        except httpx.HTTPError as e:
            return CheckResult(released=False, status_code=None, error=str(e))

        if resp.status_code != 200:
            return CheckResult(
                released=False,
                status_code=resp.status_code,
                error=f"non-200 status: {resp.status_code}",
            )

        released = _looks_released(resp.text)
        return CheckResult(released=released, status_code=200, error=None)
    finally:
        if owns_client:
            await client.aclose()
