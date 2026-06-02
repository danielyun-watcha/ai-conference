"""FastAPI app for accepted-papers release monitoring.

Endpoints:
  GET  /health
  GET  /api/accepted-papers/status
      -> current release state for every monitored conference
  POST /api/accepted-papers/check
      -> crawl every monitored conference, update SQLite, fire Slack on
         first transitions, return a summary
  POST /api/accepted-papers/check/{conference_id}
      -> same as above but scoped to one conference

n8n (later) will call POST /api/accepted-papers/check on a cron.
"""

import asyncio
import logging
from typing import Optional

import httpx
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from backend import db
from backend.conferences import MonitoredConference, load_monitored
from backend.config import CORS_ORIGINS, HTTP_TIMEOUT, USER_AGENT
from backend.crawler import CheckResult, check_url
from backend.notifier import notify_released

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

app = FastAPI(title="ai-deadlines accepted-papers monitor", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)


@app.on_event("startup")
def _startup() -> None:
    db.init_db()


class ReleaseStatus(BaseModel):
    conference_id: str
    title: str
    year: int
    url: str
    released: bool
    detected_at: Optional[str] = None
    last_checked_at: Optional[str] = None
    last_status_code: Optional[int] = None
    last_error: Optional[str] = None


class CheckSummary(BaseModel):
    checked: int
    newly_released: list[ReleaseStatus]
    already_released: list[ReleaseStatus]
    not_released: list[ReleaseStatus]


def _row_to_status(row: db.ReleaseRow) -> ReleaseStatus:
    return ReleaseStatus(
        conference_id=row.conference_id,
        title=row.title,
        year=row.year,
        url=row.url,
        released=row.released,
        detected_at=row.detected_at,
        last_checked_at=row.last_checked_at,
        last_status_code=row.last_status_code,
        last_error=row.last_error,
    )


@app.get("/health")
def health() -> dict:
    return {"ok": True}


@app.get("/api/accepted-papers/status", response_model=list[ReleaseStatus])
def get_status() -> list[ReleaseStatus]:
    return [_row_to_status(r) for r in db.list_all()]


async def _check_one(
    conf: MonitoredConference,
    http: httpx.AsyncClient,
    notify: bool,
) -> tuple[bool, db.ReleaseRow, CheckResult]:
    result = await check_url(conf.url, client=http)
    newly_released, row = db.upsert_check_result(
        conference_id=conf.id,
        title=conf.title,
        year=conf.year,
        url=conf.url,
        released_now=result.released,
        status_code=result.status_code,
        error=result.error,
    )
    if newly_released and notify:
        await notify_released(conf.title, conf.year, conf.url, client=http)
    return newly_released, row, result


async def _run_check(
    confs: list[MonitoredConference], notify: bool
) -> CheckSummary:
    newly: list[ReleaseStatus] = []
    already: list[ReleaseStatus] = []
    pending: list[ReleaseStatus] = []

    headers = {"User-Agent": USER_AGENT}
    async with httpx.AsyncClient(
        timeout=HTTP_TIMEOUT, follow_redirects=True, headers=headers
    ) as http:
        results = await asyncio.gather(
            *(_check_one(c, http, notify) for c in confs),
            return_exceptions=True,
        )

    for conf, outcome in zip(confs, results):
        if isinstance(outcome, BaseException):
            log.error("check failed for %s: %s", conf.id, outcome)
            continue
        newly_released, row, _ = outcome
        status = _row_to_status(row)
        if newly_released:
            newly.append(status)
        elif row.released:
            already.append(status)
        else:
            pending.append(status)

    return CheckSummary(
        checked=len(confs),
        newly_released=newly,
        already_released=already,
        not_released=pending,
    )


@app.post("/api/accepted-papers/check", response_model=CheckSummary)
async def check_all(notify: bool = True) -> CheckSummary:
    """Crawl every monitored conference.

    Pass ?notify=false on the very first run to seed the state without
    flooding Slack with notifications for conferences that are already public.
    """
    confs = load_monitored()
    return await _run_check(confs, notify=notify)


@app.post(
    "/api/accepted-papers/check/{conference_id}", response_model=CheckSummary
)
async def check_one(conference_id: str, notify: bool = True) -> CheckSummary:
    confs = [c for c in load_monitored() if c.id == conference_id]
    if not confs:
        raise HTTPException(
            status_code=404,
            detail=(
                f"conference '{conference_id}' not found or has no "
                "accepted_papers_url"
            ),
        )
    return await _run_check(confs, notify=notify)
