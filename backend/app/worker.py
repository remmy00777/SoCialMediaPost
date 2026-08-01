from __future__ import annotations

from celery import Celery
from celery.schedules import crontab

from app.core.config import get_settings
from app.core.db import SessionLocal
from app.services.workflow import WorkflowService
from app.services.publication import PublicationService
from app.services.scheduler import SchedulerService


settings = get_settings()
celery_app = Celery("socialmediapost", broker=settings.redis_url, backend=settings.redis_url)
celery_app.conf.update(
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    task_reject_on_worker_lost=True,
    broker_connection_retry_on_startup=True,
    timezone=settings.timezone,
    enable_utc=True,
    task_routes={"app.worker.*": {"queue": "socialmediapost"}},
)


def cron_from_expression(expression: str) -> crontab:
    minute, hour, day_of_month, month_of_year, day_of_week = expression.split()
    return crontab(
        minute=minute,
        hour=hour,
        day_of_month=day_of_month,
        month_of_year=month_of_year,
        day_of_week=day_of_week,
    )


celery_app.conf.beat_schedule = {
    "database-schedule-tick": {"task": "app.worker.schedule_tick", "schedule": crontab(minute="*")},
    "due-publications": {"task": "app.worker.publish_due_jobs", "schedule": crontab(minute="*/5")},
}



@celery_app.task(bind=True, autoretry_for=(ConnectionError,), retry_backoff=True, retry_jitter=True, max_retries=5)
def trend_discovery(self):
    with SessionLocal() as db:
        run = WorkflowService(db).run_trend_discovery()
        return {"id": run.id, "status": run.status, "summary": run.summary}


@celery_app.task(bind=True, autoretry_for=(ConnectionError,), retry_backoff=True, retry_jitter=True, max_retries=5)
def content_production(self):
    with SessionLocal() as db:
        run = WorkflowService(db).run_content_workflow()
        return {"id": run.id, "status": run.status, "summary": run.summary}


@celery_app.task(bind=True, autoretry_for=(ConnectionError,), retry_backoff=True, retry_jitter=True, max_retries=5)
def publish_one(self, job_id: str):
    with SessionLocal() as db:
        post = PublicationService(db).process(job_id, require_auto_enabled=False)
        return {"id": post.id, "platform": post.platform, "status": post.status}


@celery_app.task(bind=True)
def publish_due_jobs(self):
    from datetime import UTC, datetime
    from sqlalchemy import or_, select
    from app.models import PublicationJob
    processed = []
    with SessionLocal() as db:
        jobs = db.execute(
            select(PublicationJob).where(
                PublicationJob.status.in_(["queued", "scheduled"]),
                or_(PublicationJob.scheduled_at.is_(None), PublicationJob.scheduled_at <= datetime.now(UTC)),
            ).limit(20)
        ).scalars().all()
        for job in jobs:
            try:
                post = PublicationService(db).process(job.id, require_auto_enabled=True)
                processed.append({"job_id": job.id, "post_id": post.id, "status": post.status})
            except Exception as exc:
                processed.append({"job_id": job.id, "error": type(exc).__name__})
    return processed


@celery_app.task(bind=True)
def schedule_tick(self):
    with SessionLocal() as db:
        due = SchedulerService(db).tick()
    dispatched = []
    for workflow_type in due:
        if workflow_type == "trend_discovery":
            trend_discovery.delay(); dispatched.append(workflow_type)
        elif workflow_type == "content_production":
            content_production.delay(); dispatched.append(workflow_type)
    return {"due": due, "dispatched": dispatched}
