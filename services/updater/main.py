"""AI Deadlines Updater — auto-crawl conference deadlines daily at 9 AM KST."""

import logging
import os
import signal
import sys
from datetime import datetime, timezone, timedelta

import uvicorn
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from fastapi import FastAPI
from fastapi.responses import JSONResponse

from db import Database
from updater import run_update, UpdateResult

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(levelname)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

DATABASE_URL = os.environ.get("DATABASE_URL")
KST = timezone(timedelta(hours=9))

app = FastAPI(title="ai-deadlines-updater")
scheduler = AsyncIOScheduler()
db = Database(DATABASE_URL) if DATABASE_URL else None

_last_run: dict = {"time": None, "results": None, "error": None}


def _format_results(results: list[UpdateResult]) -> dict:
    updated = [r for r in results if r.updated]
    still_tbd = [r for r in results if not r.updated and r.error == "no deadlines found on page"]
    failed = [r for r in results if r.error and r.error != "no deadlines found on page"]
    return {
        "total_checked": len(results),
        "updated": [
            {"id": r.conf_id, "title": f"{r.title} {r.year}",
             "deadlines": [{"type": d.dtype, "date": d.date} for d in r.deadlines]}
            for r in updated
        ],
        "still_tbd": [f"{r.title} {r.year}" for r in still_tbd],
        "failed": [
            {"id": r.conf_id, "title": f"{r.title} {r.year}", "error": r.error}
            for r in failed
        ],
    }


async def _scheduled_job():
    global _last_run
    logger.info("Starting scheduled deadline update")

    if not db:
        _last_run = {"time": datetime.now(KST).isoformat(), "results": None,
                      "error": "DATABASE_URL not set"}
        logger.error("DATABASE_URL not set, skipping update")
        return

    try:
        results = await run_update(db)
        formatted = _format_results(results)
        _last_run = {"time": datetime.now(KST).isoformat(),
                      "results": formatted, "error": None}
        logger.info(
            "Update complete: %d checked, %d updated, %d still TBD, %d failed",
            formatted["total_checked"], len(formatted["updated"]),
            len(formatted["still_tbd"]), len(formatted["failed"]),
        )
    except Exception as e:
        _last_run = {"time": datetime.now(KST).isoformat(),
                      "results": None, "error": str(e)}
        logger.exception("Scheduled job failed")


@app.on_event("startup")
async def _startup():
    if db:
        db.connect()
        db.init_tables()
        logger.info("DB initialized (%d conferences, %d deadlines)",
                     db.get_conference_count(), db.get_deadline_count())

    # Daily at 9:03 AM KST = 0:03 UTC
    scheduler.add_job(
        _scheduled_job,
        CronTrigger(hour=0, minute=3, timezone="UTC"),
        id="deadline-update",
        name="Daily deadline update (9:03 AM KST)",
        replace_existing=True,
    )
    scheduler.start()
    logger.info("Scheduler started — next run at 9:03 AM KST daily")


@app.on_event("shutdown")
async def _shutdown():
    scheduler.shutdown(wait=False)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/status")
def status():
    next_run = None
    job = scheduler.get_job("deadline-update")
    if job and job.next_run_time:
        next_run = job.next_run_time.astimezone(KST).isoformat()

    return {"last_run": _last_run, "next_run_kst": next_run}


@app.get("/api/conferences")
def list_conferences():
    if not db:
        return JSONResponse({"error": "DB not configured"}, status_code=503)
    return db.get_all_conferences()


@app.get("/api/tbd")
def list_tbd():
    if not db:
        return JSONResponse({"error": "DB not configured"}, status_code=503)
    return db.get_tbd_conferences()


@app.post("/trigger")
async def trigger():
    await _scheduled_job()
    return _last_run


def _handle_sigterm(*_):
    logger.info("SIGTERM received, shutting down")
    sys.exit(0)


signal.signal(signal.SIGTERM, _handle_sigterm)

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))
