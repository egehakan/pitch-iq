"""APScheduler 3.x AsyncIOScheduler + persistent SQLAlchemyJobStore (single process only).
(canonical-spec §2 / backend-plan §6)"""
from __future__ import annotations

from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.config import Settings


def build_scheduler(s: Settings) -> AsyncIOScheduler:
    jobstores = {"default": SQLAlchemyJobStore(url=s.SYNC_DATABASE_URL, tablename="apscheduler_jobs")}
    return AsyncIOScheduler(jobstores=jobstores, timezone="UTC")
