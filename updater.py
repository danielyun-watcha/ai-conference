"""Conference deadline updater — pure crawling, no LLM API needed.

Flow:
1. Read conference YAML files from the public huggingface/ai-deadlines repo
   (no auth needed — public repo)
2. Sync conferences to local DB
3. Find entries with missing deadlines
4. Crawl CFP pages and extract dates via regex
5. Store results in DB
"""

import base64
import logging
import re
from dataclasses import dataclass, field
from typing import Optional

import httpx
import yaml
from bs4 import BeautifulSoup

from db import Database

logger = logging.getLogger(__name__)

REPO_OWNER = "huggingface"
REPO_NAME = "ai-deadlines"
CONFERENCES_PATH = "src/data/conferences"
USER_AGENT = "ai-deadlines-updater/1.0"

# ---------------------------------------------------------------------------
# Date extraction
# ---------------------------------------------------------------------------
_MONTH_NAMES = (
    r"(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|"
    r"Jul(?:y)?|Aug(?:ust)?|Sep(?:t(?:ember)?)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)"
)
_DATE_PATTERNS = [
    re.compile(rf"({_MONTH_NAMES})\s+(\d{{1,2}}),?\s+(\d{{4}})"),
    re.compile(rf"(\d{{1,2}})\s+({_MONTH_NAMES}),?\s+(\d{{4}})"),
    re.compile(r"(\d{4})-(\d{2})-(\d{2})"),
]
_DEADLINE_KEYWORDS = [
    (r"abstract\s+(?:submission|deadline|due|registration)", "abstract"),
    (r"(?:full\s+)?paper\s+(?:submission|deadline|due)", "paper"),
    (r"submission\s+(?:deadline|due)", "paper"),
    (r"notification|acceptance|decision", "notification"),
    (r"camera.?ready", "camera_ready"),
    (r"rebuttal|author\s+(?:response|feedback)", "rebuttal"),
    (r"supplementary|supp\.?\s+material", "supplementary"),
]
_MONTH_MAP = {
    "jan": 1, "january": 1, "feb": 2, "february": 2, "mar": 3, "march": 3,
    "apr": 4, "april": 4, "may": 5, "jun": 6, "june": 6,
    "jul": 7, "july": 7, "aug": 8, "august": 8, "sep": 9, "sept": 9,
    "september": 9, "oct": 10, "october": 10, "nov": 11, "november": 11,
    "dec": 12, "december": 12,
}


@dataclass
class ExtractedDeadline:
    dtype: str
    label: str
    date: str  # YYYY-MM-DD HH:MM:SS
    timezone: str = "AoE"


@dataclass
class UpdateResult:
    conf_id: str
    title: str
    year: int
    updated: bool = False
    deadlines: list[ExtractedDeadline] = field(default_factory=list)
    error: Optional[str] = None


def _parse_date_str(text: str) -> Optional[str]:
    for pat in _DATE_PATTERNS:
        m = pat.search(text)
        if not m:
            continue
        groups = m.groups()
        try:
            g0, g1, g2 = groups
            if g0.isalpha():
                month = _MONTH_MAP.get(g0.lower().rstrip("."))
                if month:
                    return f"{int(g2):04d}-{month:02d}-{int(g1):02d}"
            elif g1.isalpha():
                month = _MONTH_MAP.get(g1.lower().rstrip("."))
                if month:
                    return f"{int(g2):04d}-{month:02d}-{int(g0):02d}"
            elif len(g0) == 4:
                return f"{int(g0):04d}-{int(g1):02d}-{int(g2):02d}"
        except (ValueError, TypeError):
            continue
    return None


def _extract_deadlines(html: str, conf_year: int) -> list[ExtractedDeadline]:
    soup = BeautifulSoup(html, "html.parser")
    text_blocks: list[str] = []

    for tag in soup.find_all(["tr", "li", "dd", "dt", "p", "div", "span", "td", "th"]):
        t = tag.get_text(" ", strip=True)
        if t and len(t) < 500:
            text_blocks.append(t)

    full_text = soup.get_text("\n", strip=True)
    for line in full_text.split("\n"):
        line = line.strip()
        if line and len(line) < 500:
            text_blocks.append(line)

    seen: set[str] = set()
    unique_blocks = [b for b in text_blocks if b not in seen and not seen.add(b)]

    results: dict[str, ExtractedDeadline] = {}
    for block in unique_blocks:
        block_lower = block.lower()
        for kw_pattern, dtype in _DEADLINE_KEYWORDS:
            kw_match = re.search(kw_pattern, block_lower)
            if not kw_match:
                continue
            date_str = _parse_date_str(block)
            if not date_str:
                continue
            try:
                if abs(int(date_str[:4]) - conf_year) > 2:
                    continue
            except ValueError:
                continue

            label = block[max(0, kw_match.start() - 20):
                          min(len(block), kw_match.end() + 30)].strip()
            label = re.sub(r"\s+", " ", label)
            if len(label) > 60:
                label = label[:57] + "..."

            if dtype not in results:
                results[dtype] = ExtractedDeadline(
                    dtype=dtype, label=label, date=f"{date_str} 23:59:59",
                )
    return list(results.values())


# ---------------------------------------------------------------------------
# Sync conferences from public GitHub repo to DB
# ---------------------------------------------------------------------------
async def sync_conferences_from_github(db: Database):
    """Read all YAML files from the public repo and upsert conferences into DB."""
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(
            f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}"
            f"/contents/{CONFERENCES_PATH}"
        )
        if resp.status_code != 200:
            logger.error("Failed to list conferences: %s", resp.text[:200])
            return

        files = [f for f in resp.json() if f["name"].endswith(".yml")]
        count = 0
        for file_info in files:
            resp = await client.get(file_info["url"])
            if resp.status_code != 200:
                continue
            content = base64.b64decode(resp.json()["content"]).decode()
            data = yaml.safe_load(content)
            if not isinstance(data, list):
                continue
            for entry in data:
                if not isinstance(entry, dict):
                    continue
                conf_id = entry.get("id")
                if not conf_id:
                    continue
                db.upsert_conference(
                    conf_id=str(conf_id),
                    title=entry.get("title", ""),
                    year=int(entry.get("year", 0)),
                    link=entry.get("link"),
                    file_name=file_info["name"],
                    era_rating=entry.get("era_rating"),
                )
                # Also sync existing non-TBD deadlines
                for dl in entry.get("deadlines", []):
                    if isinstance(dl, dict) and dl.get("date") and dl["date"] != "TBD":
                        db.upsert_deadline(
                            conference_id=str(conf_id),
                            dtype=dl.get("type", "paper"),
                            label=dl.get("label", ""),
                            date=str(dl["date"]),
                            timezone=dl.get("timezone", "AoE"),
                        )
                count += 1
        logger.info("Synced %d conference entries from GitHub", count)


# ---------------------------------------------------------------------------
# Crawl
# ---------------------------------------------------------------------------
async def crawl_deadlines(link: str, year: int) -> list[ExtractedDeadline]:
    urls_to_try = [link]
    base = link.rstrip("/")
    for suffix in ["/call-for-papers", "/important-dates", "/dates",
                   "/cfp", "/call/main-technical-track"]:
        candidate = base + suffix
        if candidate != link:
            urls_to_try.append(candidate)

    async with httpx.AsyncClient(
        timeout=20, follow_redirects=True,
        headers={"User-Agent": USER_AGENT},
    ) as client:
        for url in urls_to_try:
            try:
                resp = await client.get(url)
                if resp.status_code != 200:
                    continue
                deadlines = _extract_deadlines(resp.text, year)
                if deadlines:
                    return deadlines
            except httpx.HTTPError as e:
                logger.debug("Failed to fetch %s: %s", url, e)
    return []


# ---------------------------------------------------------------------------
# Main update flow
# ---------------------------------------------------------------------------
async def run_update(db: Database) -> list[UpdateResult]:
    """Sync from GitHub → find missing deadlines → crawl → store in DB."""
    await sync_conferences_from_github(db)

    tbd = db.get_tbd_conferences()
    logger.info("Found %d conferences without deadlines", len(tbd))

    results: list[UpdateResult] = []
    for conf in tbd:
        result = UpdateResult(
            conf_id=conf["id"], title=conf["title"], year=conf["year"],
        )
        if not conf.get("link"):
            result.error = "no homepage link"
            results.append(result)
            continue

        try:
            deadlines = await crawl_deadlines(conf["link"], conf["year"])
            if not deadlines:
                result.error = "no deadlines found on page"
                results.append(result)
                continue

            result.deadlines = deadlines
            for dl in deadlines:
                db.upsert_deadline(
                    conference_id=conf["id"],
                    dtype=dl.dtype,
                    label=dl.label,
                    date=dl.date,
                    timezone=dl.timezone,
                )
            result.updated = True
        except Exception as e:
            result.error = str(e)
            logger.exception("Error updating %s", conf["id"])

        results.append(result)

    return results
