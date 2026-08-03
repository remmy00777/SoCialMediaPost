from __future__ import annotations

import csv
from dataclasses import asdict
import io
import json
import os
import secrets
import shutil
import subprocess
import tarfile
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Request, Response, UploadFile, status
from fastapi.responses import FileResponse, RedirectResponse, StreamingResponse
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from sqlalchemy import desc, func, or_, select
from sqlalchemy.orm import Session

from app.api.dependencies import CSRF_COOKIE, SESSION_COOKIE, csrf_protected, current_user
from app.core.config import get_settings
from app.core.db import engine, get_db
from app.core.logging import redact
from app.core.security import SecretBox, SessionSigner, generate_csrf_token, hash_password, secure_filename, verify_password
from app.models import (
    AccountMetricSnapshot,
    ApprovalRecord,
    AuditEvent,
    BrandProfile,
    ContentConcept,
    ContentPackage,
    ErrorEvent,
    Experiment,
    ExperimentAssignment,
    GeneratedAsset,
    Notification,
    OAuthCredential,
    OriginalityCheck,
    PlatformAccount,
    PlatformPost,
    PlatformVariant,
    PolicyCheck,
    PostMetricSnapshot,
    ProviderConfiguration,
    PublicationJob,
    Schedule,
    SourceMediaAsset,
    SourceMetric,
    SourceVideo,
    SystemSetting,
    TrendAnalysis,
    TrendCandidate,
    TrendScore,
    TrendSource,
    User,
    WorkflowRun,
)
from app.platforms.registry import registry
from app.schemas import (
    ApprovalRequest,
    AuthorizedMediaCaptureRequest,
    CreatorWatchRequest,
    BrandProfileRequest,
    ExperimentRequest,
    ImportVideoRequest,
    LoginRequest,
    PermanentDeleteRequest,
    ProviderConfigRequest,
    PublishRequest,
    ScheduleRequest,
)
from app.services.analytics import multi_objective_performance, normalized_post_metrics
from app.services.authorized_media import AuthorizedMediaError, AuthorizedMediaService
from app.services.creator_watch import CreatorWatchError, CreatorWatchService
from app.services.audit import record_audit
from app.services.experiments import deterministic_assignment
from app.services.media_validation import probe_media
from app.services.storage import PLATFORM_DISPLAY, StorageManager
from app.services.workflow import WorkflowService
from app.services.publication import PublicationService, PublicationBlocked
from app.services.scheduler import SchedulerService


router = APIRouter(prefix="/api")
settings = get_settings()
storage = StorageManager(settings)


def serialize_model(obj: Any) -> dict[str, Any]:
    return {
        column.name: getattr(obj, column.name)
        for column in obj.__table__.columns
        if column.name not in {"password_hash", "encrypted_access_token", "encrypted_refresh_token", "encrypted_secret"}
    }


@router.get("/health/liveness")
def liveness() -> dict[str, Any]:
    return {"status": "alive", "timestamp": datetime.now(UTC)}


@router.get("/health/readiness")
def readiness(db: Session = Depends(get_db)) -> dict[str, Any]:
    checks: dict[str, Any] = {}
    try:
        db.execute(select(func.count(User.id))).scalar()
        checks["database"] = "ready"
    except Exception as exc:
        checks["database"] = f"failed:{type(exc).__name__}"
    checks["ffmpeg"] = "ready" if shutil.which("ffmpeg") and shutil.which("ffprobe") else "missing"
    checks["storage"] = "ready" if storage.root.exists() and os.access(storage.root, os.W_OK) else "failed"
    checks["platforms"] = [asdict(adapter.health_check()) for adapter in registry.all()]
    ready = all(value == "ready" for key, value in checks.items() if key in {"database", "ffmpeg", "storage"})
    return {"status": "ready" if ready else "degraded", "checks": checks}


@router.get("/system/overview")
def system_overview(db: Session = Depends(get_db), _: User | None = Depends(current_user)) -> dict[str, Any]:
    latest_run = db.execute(select(WorkflowRun).order_by(desc(WorkflowRun.started_at))).scalars().first()
    accounts = db.execute(select(PlatformAccount).where(PlatformAccount.deleted_at.is_(None))).scalars().all()
    pending = db.scalar(select(func.count(ContentPackage.id)).where(ContentPackage.status.in_(["review", "draft"]))) or 0
    scheduled = db.scalar(select(func.count(PublicationJob.id)).where(PublicationJob.status == "scheduled")) or 0
    failures = db.scalar(select(func.count(PublicationJob.id)).where(PublicationJob.status == "failed")) or 0
    trends = db.execute(
        select(SourceVideo, TrendScore)
        .join(TrendCandidate, TrendCandidate.source_video_id == SourceVideo.id)
        .join(TrendScore, TrendScore.trend_candidate_id == TrendCandidate.id)
        .order_by(desc(TrendScore.score))
        .limit(5)
    ).all()
    return {
        "system_status": "paused" if get_global_pause(db) else "operational",
        "internet_status": internet_status(),
        "scheduler_status": "celery" if settings.celery_enabled else "local_configured",
        "connected_platforms": [serialize_model(account) for account in accounts],
        "latest_trends": [
            {"id": video.id, "platform": video.platform, "title": video.title, "score": score.score, "confidence": score.confidence}
            for video, score in trends
        ],
        "pending_approvals": pending,
        "scheduled_posts": scheduled,
        "publishing_failures": failures,
        "storage_usage": storage.storage_usage(),
        "last_successful_workflow": serialize_model(latest_run) if latest_run else None,
        "next_scheduled_workflow": next_schedule(db),
        "api_quota_warnings": [account.quota_status for account in accounts if account.quota_status.get("warning")],
        "token_warnings": [account.platform for account in accounts if account.token_health not in {"healthy", "unknown"}],
        "demo_mode": settings.demo_mode,
        "auto_publish_enabled": settings.auto_publish_enabled,
    }


@router.post("/auth/bootstrap")
def bootstrap(response: Response, db: Session = Depends(get_db)) -> dict[str, Any]:
    existing = db.execute(select(User)).scalars().first()
    if existing:
        raise HTTPException(status_code=409, detail="Application has already been initialized")
    user = User(email=settings.admin_email, password_hash=hash_password(settings.admin_password), is_admin=True)
    db.add(user)
    db.add(BrandProfile(user_id=user.id, approved=settings.demo_mode))
    seed_defaults(db)
    db.commit()
    set_session(response, user.id)
    return {"initialized": True, "email": user.email, "password_change_required": settings.environment != "test"}


@router.post("/auth/login")
def login(payload: LoginRequest, response: Response, db: Session = Depends(get_db)) -> dict[str, Any]:
    user = db.execute(select(User).where(User.email == payload.email)).scalar_one_or_none()
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    set_session(response, user.id)
    return {"authenticated": True, "user": {"id": user.id, "email": user.email}}


@router.post("/auth/logout", dependencies=[Depends(csrf_protected)])
def logout(response: Response) -> dict[str, bool]:
    response.delete_cookie(SESSION_COOKIE)
    response.delete_cookie(CSRF_COOKIE)
    return {"logged_out": True}


@router.get("/auth/me")
def me(user: User | None = Depends(current_user)) -> dict[str, Any]:
    return {"authenticated": bool(user), "user": {"id": user.id, "email": user.email} if user else None}


@router.get("/brand-profile")
def get_brand_profile(db: Session = Depends(get_db), _: User | None = Depends(current_user)) -> dict[str, Any]:
    profile = db.execute(select(BrandProfile).order_by(desc(BrandProfile.created_at))).scalars().first()
    return serialize_model(profile) if profile else {}


@router.put("/brand-profile", dependencies=[Depends(csrf_protected)])
def update_brand_profile(
    payload: BrandProfileRequest,
    db: Session = Depends(get_db),
    user: User | None = Depends(current_user),
) -> dict[str, Any]:
    profile = db.execute(select(BrandProfile).order_by(desc(BrandProfile.created_at))).scalars().first()
    if not profile:
        profile = BrandProfile(user_id=user.id if user else None)
        db.add(profile)
    for key, value in payload.model_dump().items():
        setattr(profile, key, value)
    record_audit(db, "brand_profile.updated", resource_type="brand_profile", resource_id=profile.id, actor_id=user.id if user else None)
    db.commit()
    return serialize_model(profile)


@router.post("/workflows/trends", dependencies=[Depends(csrf_protected)])
def run_trends(
    max_candidates: int = Query(30, ge=1, le=100),
    select_limit: int = Query(10, ge=1, le=10),
    db: Session = Depends(get_db),
    _: User | None = Depends(current_user),
) -> dict[str, Any]:
    run = WorkflowService(db).run_trend_discovery(max_candidates=max_candidates, select_limit=select_limit)
    return serialize_model(run)


@router.post("/workflows/content", dependencies=[Depends(csrf_protected)])
def run_content(
    max_items: int = Query(10, ge=1, le=10),
    db: Session = Depends(get_db),
    _: User | None = Depends(current_user),
) -> dict[str, Any]:
    run = WorkflowService(db).run_content_workflow(max_items=max_items)
    return serialize_model(run)


@router.post("/workflows/demo", dependencies=[Depends(csrf_protected)])
def run_demo(db: Session = Depends(get_db), user: User | None = Depends(current_user)) -> dict[str, Any]:
    trend_run = WorkflowService(db).run_trend_discovery(max_candidates=10, select_limit=1)
    content_run = WorkflowService(db).run_content_workflow(max_items=1)
    package = db.execute(select(ContentPackage).order_by(desc(ContentPackage.created_at))).scalars().first()
    simulated_job = None
    analytics_snapshot = None
    if package:
        simulated_job = publish_package(
            package.id,
            PublishRequest(platform="tiktok", simulate=True),
            db,
            user,
        )
        analytics_snapshot = populate_demo_analytics(db, user)
    return {
        "demonstration": True,
        "trend_run": serialize_model(trend_run),
        "content_run": serialize_model(content_run),
        "package": serialize_model(package) if package else None,
        "simulated_publication": simulated_job,
        "sample_analytics": analytics_snapshot,
    }


@router.get("/workflows")
def list_workflows(db: Session = Depends(get_db), _: User | None = Depends(current_user)) -> list[dict[str, Any]]:
    return [serialize_model(item) for item in db.execute(select(WorkflowRun).order_by(desc(WorkflowRun.started_at)).limit(100)).scalars()]


@router.get("/trends")
def list_trends(db: Session = Depends(get_db), _: User | None = Depends(current_user)) -> list[dict[str, Any]]:
    rows = db.execute(
        select(SourceVideo, TrendCandidate, TrendScore, TrendSource)
        .join(TrendCandidate, TrendCandidate.source_video_id == SourceVideo.id)
        .join(TrendScore, TrendScore.trend_candidate_id == TrendCandidate.id)
        .outerjoin(TrendSource, TrendCandidate.trend_source_id == TrendSource.id)
        .order_by(desc(TrendCandidate.created_at), desc(TrendScore.score))
    ).all()
    return [
        {
            **serialize_model(video),
            "candidate_id": candidate.id,
            "selected": candidate.selected,
            "rank": candidate.rank,
            "score": score.score,
            "score_confidence": score.confidence,
            "score_components": score.components,
            "score_explanation": score.explanation,
            "missing_metrics": score.missing_metrics,
            "source_label": source.label if source else video.data_source,
            "source_limitations": source.limitations if source else None,
        }
        for video, candidate, score, source in rows
    ]


@router.get("/trends/{candidate_id}")
def trend_detail(candidate_id: str, db: Session = Depends(get_db), _: User | None = Depends(current_user)) -> dict[str, Any]:
    candidate = db.get(TrendCandidate, candidate_id)
    if not candidate:
        raise HTTPException(404, "Trend candidate not found")
    video = db.get(SourceVideo, candidate.source_video_id)
    score = db.execute(select(TrendScore).where(TrendScore.trend_candidate_id == candidate.id)).scalar_one_or_none()
    analysis = db.execute(select(TrendAnalysis).where(TrendAnalysis.trend_candidate_id == candidate.id)).scalar_one_or_none()
    concepts = db.execute(select(ContentConcept).where(ContentConcept.trend_candidate_id == candidate.id)).scalars().all()
    metrics = db.execute(select(SourceMetric).where(SourceMetric.source_video_id == candidate.source_video_id).order_by(desc(SourceMetric.retrieved_at))).scalars().all()
    return {
        "video": serialize_model(video),
        "candidate": serialize_model(candidate),
        "score": serialize_model(score) if score else None,
        "analysis": serialize_model(analysis) if analysis else None,
        "concepts": [serialize_model(item) for item in concepts],
        "metric_snapshots": [serialize_model(item) for item in metrics],
    }


@router.post("/trends/import", dependencies=[Depends(csrf_protected)])
def import_trend(payload: ImportVideoRequest, db: Session = Depends(get_db), _: User | None = Depends(current_user)) -> dict[str, Any]:
    adapter = registry.get(payload.platform)
    video = adapter.import_video_reference(payload.url)
    updates = payload.model_dump(exclude={"platform", "url", "metrics"}, exclude_none=True)
    for key, value in updates.items():
        setattr(video, key, value)
    video.metrics = payload.metrics
    video.data_source = "manual_url_import"
    service = WorkflowService(db)
    source = service._upsert_source_video(video)
    source_record = service._get_or_create_trend_source(video)
    candidate = TrendCandidate(source_video_id=source.id, trend_source_id=source_record.id, selected=True)
    db.add(candidate)
    db.flush()
    score_result = service.scorer.score(video)
    db.add(TrendScore(trend_candidate_id=candidate.id, **score_result.model_dump()))
    record_audit(db, "trend.imported", resource_type="trend_candidate", resource_id=candidate.id)
    db.commit()
    return {"candidate_id": candidate.id, "video_id": source.id, "score": score_result.model_dump()}


@router.get("/creator-watchlist")
def list_creator_watchlist(
    db: Session = Depends(get_db),
    user: User | None = Depends(current_user),
) -> list[dict[str, Any]]:
    rows = db.execute(
        select(TrendSource)
        .where(
            TrendSource.source_type == "creator_watch",
            TrendSource.deleted_at.is_(None),
        )
        .order_by(desc(TrendSource.created_at))
    ).scalars().all()
    result = []
    for row in rows:
        configuration = dict(row.configuration or {})
        if user and configuration.get("user_id") not in {None, user.id}:
            continue
        configuration.pop("user_id", None)
        result.append({**serialize_model(row), "configuration": configuration})
    return result


@router.post("/creator-watchlist", dependencies=[Depends(csrf_protected)])
def create_creator_watch(
    payload: CreatorWatchRequest,
    db: Session = Depends(get_db),
    user: User | None = Depends(current_user),
) -> dict[str, Any]:
    if payload.auto_capture_and_prepare:
        if not payload.allow_full_reuse:
            raise HTTPException(422, "Automatic capture requires full-reuse authorization")
        if not payload.authorized_media_url_template:
            raise HTTPException(422, "Automatic capture requires an authorized media URL template")
    if (
        payload.rights_status in {"licensed", "public_domain", "explicit_permission"}
        and not payload.license_reference
    ):
        raise HTTPException(422, "License, permission, or public-domain reference is required")

    configuration = payload.model_dump(mode="json")
    configuration["user_id"] = user.id if user else None
    watch = TrendSource(
        platform=payload.platform,
        source_type="creator_watch",
        label=payload.creator_name,
        active=True,
        limitations=(
            "YouTube supports official upload polling. Instagram and TikTok require "
            "creator authorization or a licensed media feed. Full media is acquired only "
            "from an allowlisted authorized delivery host."
        ),
        configuration=configuration,
    )
    db.add(watch)
    db.flush()
    record_audit(
        db,
        "creator_watch.created",
        resource_type="trend_source",
        resource_id=watch.id,
        actor_id=user.id if user else None,
        event_data={
            "platform": payload.platform,
            "external_creator_id": payload.external_creator_id,
            "auto_capture_and_prepare": payload.auto_capture_and_prepare,
        },
    )
    db.commit()
    return serialize_model(watch)


@router.post("/creator-watchlist/{watch_id}/check", dependencies=[Depends(csrf_protected)])
def check_creator_watch(
    watch_id: str,
    db: Session = Depends(get_db),
    _: User | None = Depends(current_user),
) -> dict[str, Any]:
    try:
        return CreatorWatchService(db).check_watch(watch_id)
    except CreatorWatchError as exc:
        raise HTTPException(409, str(exc)) from exc


@router.delete("/creator-watchlist/{watch_id}", dependencies=[Depends(csrf_protected)])
def disable_creator_watch(
    watch_id: str,
    db: Session = Depends(get_db),
    user: User | None = Depends(current_user),
) -> dict[str, bool]:
    watch = db.get(TrendSource, watch_id)
    if not watch or watch.source_type != "creator_watch":
        raise HTTPException(404, "Creator watch was not found")
    watch.active = False
    watch.deleted_at = datetime.now(UTC)
    record_audit(
        db,
        "creator_watch.disabled",
        resource_type="trend_source",
        resource_id=watch.id,
        actor_id=user.id if user else None,
    )
    db.commit()
    return {"disabled": True}


@router.post(
    "/trends/{candidate_id}/remix",
    dependencies=[Depends(csrf_protected)],
)
def remix_trend_as_new_post(
    candidate_id: str,
    db: Session = Depends(get_db),
    _: User | None = Depends(current_user),
) -> dict[str, Any]:
    try:
        package = WorkflowService(db).run_candidate_remix(candidate_id)
    except RuntimeError as exc:
        raise HTTPException(409, str(exc)) from exc

    return {
        "created": True,
        "candidate_id": candidate_id,
        "package_id": package.id,
        "title": package.title,
        "status": package.status,
        "message": "A new cross-platform post package was created.",
    }


AUTHORIZED_SOURCE_RIGHTS = {"user_owned", "licensed", "public_domain", "explicit_permission"}
ALLOWED_SOURCE_MIME_TYPES = {"video/mp4", "video/quicktime", "video/webm", "video/x-m4v"}
ALLOWED_SOURCE_SUFFIXES = {".mp4", ".mov", ".webm", ".m4v"}


@router.get("/trends/{candidate_id}/source-media")
def get_source_media(
    candidate_id: str,
    db: Session = Depends(get_db),
    _: User | None = Depends(current_user),
) -> dict[str, Any]:
    candidate = db.get(TrendCandidate, candidate_id)
    if not candidate:
        raise HTTPException(404, "Trend candidate not found")
    asset = db.execute(
        select(SourceMediaAsset)
        .where(
            SourceMediaAsset.source_video_id == candidate.source_video_id,
            SourceMediaAsset.deleted_at.is_(None),
        )
        .order_by(desc(SourceMediaAsset.created_at))
    ).scalars().first()
    return {"source_media": serialize_model(asset) if asset else None}


@router.post(
    "/trends/{candidate_id}/source-media/capture-url",
    dependencies=[Depends(csrf_protected)],
)
def capture_source_media_url(
    candidate_id: str,
    payload: AuthorizedMediaCaptureRequest,
    db: Session = Depends(get_db),
    user: User | None = Depends(current_user),
) -> dict[str, Any]:
    try:
        asset = AuthorizedMediaService(db).capture_for_candidate(
            candidate_id,
            source_url=str(payload.source_url),
            rights_status=payload.rights_status,
            rights_owner=payload.rights_owner,
            license_reference=payload.license_reference,
            attribution_text=payload.attribution_text,
            allow_full_reuse=payload.allow_full_reuse,
            user_id=user.id if user else None,
        )
    except AuthorizedMediaError as exc:
        raise HTTPException(422, str(exc)) from exc
    return {
        "source_media": serialize_model(asset),
        "message": "Full authorized source captured and stored for manual-post generation",
    }


@router.post("/trends/{candidate_id}/source-media", dependencies=[Depends(csrf_protected)])
async def upload_source_media(
    candidate_id: str,
    file: UploadFile = File(...),
    rights_status: str = Form(...),
    rights_owner: str = Form(...),
    license_reference: str | None = Form(None),
    allow_full_reuse: bool = Form(False),
    db: Session = Depends(get_db),
    user: User | None = Depends(current_user),
) -> dict[str, Any]:
    candidate = db.get(TrendCandidate, candidate_id)
    if not candidate:
        raise HTTPException(404, "Trend candidate not found")
    if rights_status not in AUTHORIZED_SOURCE_RIGHTS:
        raise HTTPException(422, "Rights status must be user_owned, licensed, public_domain, or explicit_permission")
    if not allow_full_reuse:
        raise HTTPException(422, "Full reuse must be explicitly authorized before the source clip can be included")
    if rights_status in {"licensed", "public_domain", "explicit_permission"} and not license_reference:
        raise HTTPException(422, "A license, public-domain, or permission reference is required")
    if not rights_owner.strip():
        raise HTTPException(422, "Rights owner is required")

    original_name = secure_filename(file.filename or "source.mp4")
    suffix = Path(original_name).suffix.lower()
    mime_type = (file.content_type or "").lower()
    if suffix not in ALLOWED_SOURCE_SUFFIXES or mime_type not in ALLOWED_SOURCE_MIME_TYPES:
        raise HTTPException(415, "Only MP4, MOV, M4V, or WebM video uploads are accepted")

    directory = storage.source_media_dir(candidate_id)
    destination = storage.ensure_inside_root(directory / f"source-{secrets.token_hex(8)}{suffix}")
    temporary = storage.ensure_inside_root(directory / f".{destination.name}.uploading")
    size = 0
    try:
        with temporary.open("wb") as handle:
            while chunk := await file.read(1024 * 1024):
                size += len(chunk)
                if size > settings.source_media_max_bytes:
                    raise HTTPException(413, "Source media exceeds the configured upload limit")
                handle.write(chunk)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, destination)
    except Exception:
        temporary.unlink(missing_ok=True)
        destination.unlink(missing_ok=True)
        raise
    finally:
        await file.close()

    validation = probe_media(destination)
    duration = float(validation.get("duration") or 0)
    if not validation.get("valid") or duration <= 0:
        destination.unlink(missing_ok=True)
        raise HTTPException(422, "Uploaded source media failed FFmpeg validation")
    if duration > settings.source_media_max_duration_seconds:
        destination.unlink(missing_ok=True)
        raise HTTPException(422, f"Source clip exceeds the {settings.source_media_max_duration_seconds}-second full-reuse limit")

    existing = db.execute(
        select(SourceMediaAsset).where(
            SourceMediaAsset.source_video_id == candidate.source_video_id,
            SourceMediaAsset.deleted_at.is_(None),
        )
    ).scalars().all()
    for old in existing:
        old_path = Path(old.path)
        try:
            storage.ensure_inside_root(old_path).unlink(missing_ok=True)
        except ValueError:
            pass
        old.deleted_at = datetime.now(UTC)

    asset = SourceMediaAsset(
        source_video_id=candidate.source_video_id,
        uploaded_by_user_id=user.id if user else None,
        original_filename=original_name,
        path=str(destination),
        mime_type=mime_type,
        size_bytes=size,
        sha256=storage.sha256(destination),
        media_validation=validation,
        rights_status=rights_status,
        rights_owner=rights_owner.strip(),
        license_reference=license_reference.strip() if license_reference else None,
        allow_full_reuse=True,
        rights_verified_at=datetime.now(UTC),
    )
    db.add(asset)
    db.flush()
    record_audit(
        db,
        "source_media.uploaded",
        resource_type="source_media_asset",
        resource_id=asset.id,
        actor_id=user.id if user else None,
        event_data={
            "candidate_id": candidate_id,
            "rights_status": rights_status,
            "size_bytes": size,
            "duration_seconds": duration,
        },
    )
    db.commit()
    return {"source_media": serialize_model(asset), "message": "Authorized source clip stored for voiceover-intro generation"}


@router.delete("/trends/{candidate_id}/source-media", dependencies=[Depends(csrf_protected)])
def delete_source_media(
    candidate_id: str,
    payload: PermanentDeleteRequest,
    db: Session = Depends(get_db),
    user: User | None = Depends(current_user),
) -> dict[str, Any]:
    candidate = db.get(TrendCandidate, candidate_id)
    if not candidate:
        raise HTTPException(404, "Trend candidate not found")
    assets = db.execute(
        select(SourceMediaAsset).where(
            SourceMediaAsset.source_video_id == candidate.source_video_id,
            SourceMediaAsset.deleted_at.is_(None),
        )
    ).scalars().all()
    stats = {"files_deleted": 0, "bytes_freed": 0, "directories_deleted": 0}
    parents: set[Path] = set()
    for asset in assets:
        try:
            path = storage.ensure_inside_root(Path(asset.path))
            if path.is_file():
                stats["bytes_freed"] += path.stat().st_size
                path.unlink()
                stats["files_deleted"] += 1
                parents.add(path.parent)
        except ValueError:
            pass
        db.delete(asset)
    for parent in parents:
        try:
            parent.rmdir()
            stats["directories_deleted"] += 1
        except OSError:
            pass
    record_audit(
        db,
        "source_media.permanently_deleted",
        resource_type="trend_candidate",
        resource_id=candidate_id,
        actor_id=user.id if user else None,
        event_data=stats,
    )
    db.commit()
    return {"deleted": True, **stats}


@router.get("/content-packages")
def list_packages(db: Session = Depends(get_db), _: User | None = Depends(current_user)) -> list[dict[str, Any]]:
    packages = db.execute(select(ContentPackage).order_by(desc(ContentPackage.created_at))).scalars().all()
    result = []
    for package in packages:
        variants = db.execute(select(PlatformVariant).where(PlatformVariant.content_package_id == package.id)).scalars().all()
        storage_bytes = db.scalar(
            select(func.coalesce(func.sum(GeneratedAsset.size_bytes), 0)).where(GeneratedAsset.content_package_id == package.id)
        ) or 0
        result.append(
            {
                **serialize_model(package),
                "storage_bytes": int(storage_bytes),
                "variants": [serialize_model(item) for item in variants],
            }
        )
    return result


@router.get("/content-packages/{package_id}")
def package_detail(package_id: str, db: Session = Depends(get_db), _: User | None = Depends(current_user)) -> dict[str, Any]:
    package = db.get(ContentPackage, package_id)
    if not package:
        raise HTTPException(404, "Content package not found")
    variants = db.execute(select(PlatformVariant).where(PlatformVariant.content_package_id == package.id)).scalars().all()
    approvals = db.execute(select(ApprovalRecord).where(ApprovalRecord.content_package_id == package.id)).scalars().all()
    return {**serialize_model(package), "variants": [serialize_model(item) for item in variants], "approvals": [serialize_model(item) for item in approvals]}


@router.delete("/content-packages/{package_id}/permanent", dependencies=[Depends(csrf_protected)])
def permanently_delete_package(
    package_id: str,
    payload: PermanentDeleteRequest,
    db: Session = Depends(get_db),
    user: User | None = Depends(current_user),
) -> dict[str, Any]:
    package = db.get(ContentPackage, package_id)
    if not package:
        raise HTTPException(404, "Content package not found")

    variant_ids = list(
        db.execute(
            select(PlatformVariant.id).where(PlatformVariant.content_package_id == package_id)
        ).scalars()
    )
    jobs = (
        db.execute(select(PublicationJob).where(PublicationJob.platform_variant_id.in_(variant_ids))).scalars().all()
        if variant_ids
        else []
    )
    job_ids = [job.id for job in jobs]
    posts = (
        db.execute(select(PlatformPost).where(PlatformPost.publication_job_id.in_(job_ids))).scalars().all()
        if job_ids
        else []
    )
    post_ids = [post.id for post in posts]
    concept_id = package.concept_id
    stats = storage.delete_content_package(package_id)

    if post_ids:
        db.query(PostMetricSnapshot).filter(PostMetricSnapshot.platform_post_id.in_(post_ids)).delete(
            synchronize_session=False
        )
    if job_ids:
        db.query(PlatformPost).filter(PlatformPost.publication_job_id.in_(job_ids)).delete(
            synchronize_session=False
        )
    if variant_ids:
        db.query(PublicationJob).filter(PublicationJob.platform_variant_id.in_(variant_ids)).delete(
            synchronize_session=False
        )
    db.query(GeneratedAsset).filter(GeneratedAsset.content_package_id == package_id).delete(
        synchronize_session=False
    )
    db.query(ApprovalRecord).filter(ApprovalRecord.content_package_id == package_id).delete(
        synchronize_session=False
    )
    db.query(ExperimentAssignment).filter(ExperimentAssignment.content_package_id == package_id).delete(
        synchronize_session=False
    )
    db.query(PolicyCheck).filter(PolicyCheck.content_package_id == package_id).delete(
        synchronize_session=False
    )
    db.query(OriginalityCheck).filter(OriginalityCheck.content_package_id == package_id).delete(
        synchronize_session=False
    )
    db.query(PlatformVariant).filter(PlatformVariant.content_package_id == package_id).delete(
        synchronize_session=False
    )
    db.delete(package)
    db.flush()
    remaining = db.scalar(select(func.count(ContentPackage.id)).where(ContentPackage.concept_id == concept_id)) or 0
    if not remaining:
        concept = db.get(ContentConcept, concept_id)
        if concept:
            db.delete(concept)
    record_audit(
        db,
        "content_package.permanently_deleted",
        resource_type="content_package",
        resource_id=package_id,
        actor_id=user.id if user else None,
        event_data={
            **stats,
            "remote_posts_deleted": False,
            "warning": "Any post already published on a social platform remains online until removed through that platform.",
        },
    )
    db.commit()
    return {
        "deleted": True,
        "package_id": package_id,
        **stats,
        "remote_posts_deleted": False,
    }


@router.post("/content-packages/{package_id}/approve", dependencies=[Depends(csrf_protected)])
def approve_package(
    package_id: str,
    payload: ApprovalRequest,
    db: Session = Depends(get_db),
    user: User | None = Depends(current_user),
) -> dict[str, Any]:
    package = db.get(ContentPackage, package_id)
    if not package:
        raise HTTPException(404, "Content package not found")
    variants = db.execute(select(PlatformVariant).where(PlatformVariant.content_package_id == package.id)).scalars().all()
    for variant in variants:
        old = Path(variant.media_path).parent if variant.media_path else None
        if old and old.exists() and old.parent.name == "drafts":
            target = storage.move_package(variant.platform, package.id, "drafts", "ready_to_post")
            variant.media_path = str(target / "final_video.mp4")
            variant.thumbnail_path = str(target / "thumbnail.png")
            variant.subtitle_path = str(target / "subtitles.srt")
            storage.mirror_ready_package(variant.platform, target, package.id)
        variant.status = "ready_to_post"
    package.status = "ready_to_post"
    db.add(ApprovalRecord(content_package_id=package.id, user_id=user.id if user else None, action="approved", reason=payload.reason))
    record_audit(db, "content_package.approved", resource_type="content_package", resource_id=package.id, actor_id=user.id if user else None)
    db.commit()
    return serialize_model(package)


@router.post("/content-packages/{package_id}/reject", dependencies=[Depends(csrf_protected)])
def reject_package(
    package_id: str,
    payload: ApprovalRequest,
    db: Session = Depends(get_db),
    user: User | None = Depends(current_user),
) -> dict[str, Any]:
    package = db.get(ContentPackage, package_id)
    if not package:
        raise HTTPException(404, "Content package not found")
    package.status = "archived"
    db.add(ApprovalRecord(content_package_id=package.id, user_id=user.id if user else None, action="rejected", reason=payload.reason))
    record_audit(db, "content_package.rejected", resource_type="content_package", resource_id=package.id, actor_id=user.id if user else None)
    db.commit()
    return serialize_model(package)


@router.post("/content-packages/{package_id}/publish", dependencies=[Depends(csrf_protected)])
def publish_package(
    package_id: str,
    payload: PublishRequest,
    db: Session = Depends(get_db),
    user: User | None = Depends(current_user),
) -> dict[str, Any]:
    package = db.get(ContentPackage, package_id)
    if not package:
        raise HTTPException(404, "Content package not found")
    variant = db.execute(select(PlatformVariant).where(PlatformVariant.content_package_id == package.id, PlatformVariant.platform == payload.platform)).scalar_one_or_none()
    if not variant:
        raise HTTPException(404, "Platform variant not found")
    if package.status not in {"ready_to_post", "approved", "scheduled"}:
        raise HTTPException(409, "Package has not passed review and approval")
    if payload.platform_account_id:
        account = db.get(PlatformAccount, payload.platform_account_id)
        if not account or account.deleted_at is not None:
            raise HTTPException(404, "Selected platform account not found")
        if account.platform != payload.platform:
            raise HTTPException(409, "Selected account does not match the requested platform")
        if user and account.user_id and account.user_id != user.id:
            raise HTTPException(403, "Selected account belongs to another application user")
        if account.authorization_status != "connected":
            raise HTTPException(409, "Selected platform account is not connected")
    else:
        account = db.execute(
            select(PlatformAccount).where(
                PlatformAccount.platform == payload.platform,
                PlatformAccount.authorization_status == "connected",
                PlatformAccount.deleted_at.is_(None),
                or_(
                    PlatformAccount.user_id == (user.id if user else None),
                    PlatformAccount.user_id.is_(None),
                ),
            )
        ).scalars().first()
    key = f"publish:{variant.id}:{account.id if account else 'none'}:{payload.schedule_at or 'now'}"
    existing = db.execute(select(PublicationJob).where(PublicationJob.idempotency_key == key)).scalar_one_or_none()
    if existing:
        return serialize_model(existing)
    job = PublicationJob(
        platform_variant_id=variant.id,
        platform_account_id=account.id if account else None,
        scheduled_at=payload.schedule_at,
        status="scheduled" if payload.schedule_at else "queued",
        idempotency_key=key,
    )
    db.add(job)
    db.flush()
    if payload.simulate:
        post = PlatformPost(
            publication_job_id=job.id,
            platform=payload.platform,
            external_post_id=f"simulated-{secrets.token_hex(8)}",
            canonical_url=None,
            published_at=datetime.now(UTC),
            status="simulated",
            raw_response={"simulated": True, "never_sent_to_platform": True},
        )
        db.add(post)
        job.status = "simulated"
        variant.status = "simulated_published"
    else:
        record_audit(db, "publication.queued", resource_type="publication_job", resource_id=job.id, actor_id=user.id if user else None)
        db.commit()
        if payload.schedule_at and payload.schedule_at > datetime.now(UTC):
            return serialize_model(job)
        if settings.celery_enabled:
            from app.worker import publish_one
            publish_one.delay(job.id)
            return serialize_model(job)
        try:
            post = PublicationService(db).process(job.id, require_auto_enabled=False)
            return {**serialize_model(job), "platform_post": serialize_model(post)}
        except PublicationBlocked as exc:
            raise HTTPException(409, str(exc)) from exc
        except Exception as exc:
            raise HTTPException(502, f"Official platform publication failed: {type(exc).__name__}") from exc
    record_audit(db, "publication.simulated", resource_type="publication_job", resource_id=job.id, actor_id=user.id if user else None)
    db.commit()
    return serialize_model(job)


@router.get("/files")
def get_file(
    path: str,
    _: User | None = Depends(current_user),
) -> FileResponse:
    requested = Path(path)
    resolved = storage.ensure_inside_root(requested if requested.is_absolute() else storage.root / requested)
    if not resolved.exists() or not resolved.is_file():
        raise HTTPException(404, "File not found")
    return FileResponse(resolved)


@router.get("/accounts")
def accounts(db: Session = Depends(get_db), user: User | None = Depends(current_user)) -> list[dict[str, Any]]:
    records = db.execute(
        select(PlatformAccount)
        .where(
            PlatformAccount.deleted_at.is_(None),
            or_(
                PlatformAccount.user_id == (user.id if user else None),
                PlatformAccount.user_id.is_(None),
            ),
        )
        .order_by(PlatformAccount.platform, PlatformAccount.created_at)
    ).scalars().all()
    grouped: dict[str, list[dict[str, Any]]] = {}
    adopted = False
    for item in records:
        if user and item.user_id is None:
            item.user_id = user.id
            adopted = True
        grouped.setdefault(item.platform, []).append(serialize_model(item))
    if adopted:
        db.commit()
    result = []
    for adapter in registry.all():
        health = adapter.health_check()
        platform_accounts = grouped.get(adapter.platform, [])
        result.append(
            {
                "platform": adapter.platform,
                "health": asdict(health),
                "accounts": platform_accounts,
                "account": platform_accounts[0] if platform_accounts else None,
                "multiple_accounts_supported": True,
            }
        )
    return result


@router.post("/accounts/{platform}/connect", dependencies=[Depends(csrf_protected)])
def connect_account(platform: str, db: Session = Depends(get_db), user: User | None = Depends(current_user)) -> dict[str, str]:
    adapter = registry.get(platform)
    state = SessionSigner().issue(f"oauth:{platform}:{user.id if user else 'local'}", ttl_minutes=15)
    return {"authorization_url": adapter.connect_account(state)}


@router.get("/accounts/{platform}/callback")
def oauth_callback(
    platform: str,
    code: str,
    state: str,
    request: Request,
    db: Session = Depends(get_db),
) -> RedirectResponse:
    payload = SessionSigner().verify(state)
    subject = str(payload["sub"])
    if not subject.startswith(f"oauth:{platform}:"):
        raise HTTPException(400, "Invalid OAuth state")
    user_id = subject.split(":", 2)[2]
    if user_id == "local":
        user_id = ""
    elif not db.get(User, user_id):
        raise HTTPException(400, "OAuth state references an unknown application user")

    adapter = registry.get(platform)
    exchange = getattr(adapter, "exchange_code")(code)
    access_token = exchange.get("access_token")
    if not access_token:
        raise HTTPException(400, "OAuth provider did not return an access token")
    verification = adapter.verify_permissions(access_token)
    account_infos = verification.get("accounts") or [verification.get("account") or {}]
    connected_ids: list[str] = []
    box = SecretBox()
    for account_info in account_infos:
        external_id = str(
            account_info.get("id")
            or account_info.get("open_id")
            or account_info.get("instagram_business_account", {}).get("id")
            or secrets.token_hex(8)
        )
        display = (
            account_info.get("snippet", {}).get("title")
            or account_info.get("display_name")
            or account_info.get("name")
            or platform.title()
        )
        account = db.execute(
            select(PlatformAccount).where(
                PlatformAccount.platform == platform,
                PlatformAccount.external_account_id == external_id,
                PlatformAccount.deleted_at.is_(None),
            )
        ).scalar_one_or_none()
        if not account:
            account = PlatformAccount(platform=platform, external_account_id=external_id)
            db.add(account)
        account.user_id = user_id or None
        account.display_name = display
        account.authorization_status = "connected"
        account.token_health = "healthy"
        account.granted_permissions = verification.get("required_scopes", [])
        account.missing_permissions = []
        account.publishing_eligible = bool(verification.get("valid"))
        account.analytics_eligible = bool(verification.get("valid"))
        account.raw_profile = account_info
        account.account_type = account_info.get("account_type") or account_info.get(
            "instagram_business_account", {}
        ).get("account_type")
        account.app_review_required = platform in {"tiktok", "instagram"}
        account.last_api_call_at = datetime.now(UTC)
        db.flush()

        credential = db.execute(
            select(OAuthCredential).where(OAuthCredential.platform_account_id == account.id)
        ).scalar_one_or_none()
        if not credential:
            credential = OAuthCredential(platform_account_id=account.id)
            db.add(credential)
        credential.encrypted_access_token = box.encrypt(access_token)
        if exchange.get("refresh_token"):
            credential.encrypted_refresh_token = box.encrypt(exchange["refresh_token"])
        credential.token_type = exchange.get("token_type")
        credential.scopes = (
            exchange.get("scope", "").split()
            if isinstance(exchange.get("scope"), str)
            else exchange.get("scope", [])
        )
        if exchange.get("expires_in"):
            credential.expires_at = datetime.now(UTC) + timedelta(seconds=int(exchange["expires_in"]))
        connected_ids.append(account.id)
        record_audit(
            db,
            "platform_account.connected",
            resource_type="platform_account",
            resource_id=account.id,
            actor_id=user_id or None,
        )
    db.commit()
    portal_url = f"{settings.public_base_url.rstrip('/')}/portal/#accounts"
    return RedirectResponse(url=portal_url)


def _platform_account_for_user(
    db: Session, account_id: str, user: User | None
) -> PlatformAccount:
    account = db.get(PlatformAccount, account_id)
    if not account or account.deleted_at is not None:
        raise HTTPException(404, "Platform account not found")
    if user and account.user_id and account.user_id != user.id:
        raise HTTPException(403, "Platform account belongs to another application user")
    return account


def _test_platform_account(db: Session, account: PlatformAccount) -> dict[str, Any]:
    credential = db.execute(
        select(OAuthCredential).where(OAuthCredential.platform_account_id == account.id)
    ).scalar_one_or_none()
    if not credential or not credential.encrypted_access_token:
        raise HTTPException(409, "Access token unavailable")
    token = SecretBox().decrypt(credential.encrypted_access_token)
    result = registry.get(account.platform).verify_permissions(token)
    account.last_api_call_at = datetime.now(UTC)
    account.token_health = "healthy" if result.get("valid") else "degraded"
    db.commit()
    return redact(result)


def _disconnect_platform_account(db: Session, account: PlatformAccount) -> dict[str, bool]:
    credential = db.execute(
        select(OAuthCredential).where(OAuthCredential.platform_account_id == account.id)
    ).scalar_one_or_none()
    if credential:
        db.delete(credential)
    account.authorization_status = "disconnected"
    account.token_health = "unknown"
    account.publishing_eligible = False
    db.commit()
    return {"disconnected": True}


@router.post("/platform-accounts/{account_id}/test", dependencies=[Depends(csrf_protected)])
def test_platform_account(
    account_id: str,
    db: Session = Depends(get_db),
    user: User | None = Depends(current_user),
) -> dict[str, Any]:
    return _test_platform_account(db, _platform_account_for_user(db, account_id, user))


@router.post("/platform-accounts/{account_id}/disconnect", dependencies=[Depends(csrf_protected)])
def disconnect_platform_account(
    account_id: str,
    db: Session = Depends(get_db),
    user: User | None = Depends(current_user),
) -> dict[str, bool]:
    return _disconnect_platform_account(db, _platform_account_for_user(db, account_id, user))


@router.post("/accounts/{platform}/test", dependencies=[Depends(csrf_protected)])
def test_account(
    platform: str,
    db: Session = Depends(get_db),
    user: User | None = Depends(current_user),
) -> dict[str, Any]:
    account = db.execute(
        select(PlatformAccount).where(
            PlatformAccount.platform == platform,
            or_(
                PlatformAccount.user_id == (user.id if user else None),
                PlatformAccount.user_id.is_(None),
            ),
            PlatformAccount.deleted_at.is_(None),
        )
    ).scalars().first()
    if not account:
        raise HTTPException(404, "Account not connected")
    return _test_platform_account(db, account)


@router.post("/accounts/{platform}/disconnect", dependencies=[Depends(csrf_protected)])
def disconnect_account(
    platform: str,
    db: Session = Depends(get_db),
    user: User | None = Depends(current_user),
) -> dict[str, bool]:
    account = db.execute(
        select(PlatformAccount).where(
            PlatformAccount.platform == platform,
            or_(
                PlatformAccount.user_id == (user.id if user else None),
                PlatformAccount.user_id.is_(None),
            ),
            PlatformAccount.deleted_at.is_(None),
        )
    ).scalars().first()
    if not account:
        return {"disconnected": True}
    return _disconnect_platform_account(db, account)


@router.get("/schedules")
def schedules(db: Session = Depends(get_db), _: User | None = Depends(current_user)) -> list[dict[str, Any]]:
    return [serialize_model(item) for item in db.execute(select(Schedule).order_by(Schedule.name)).scalars()]


@router.put("/schedules/{name}", dependencies=[Depends(csrf_protected)])
def update_schedule(name: str, payload: ScheduleRequest, db: Session = Depends(get_db), _: User | None = Depends(current_user)) -> dict[str, Any]:
    try:
        SchedulerService.validate(payload.cron_expression, payload.timezone)
    except (ValueError, KeyError) as exc:
        raise HTTPException(422, str(exc)) from exc
    schedule = db.execute(select(Schedule).where(Schedule.name == name)).scalar_one_or_none()
    if not schedule:
        schedule = Schedule(name=name, workflow_type=name)
        db.add(schedule)
    schedule.cron_expression = payload.cron_expression
    schedule.timezone = payload.timezone
    schedule.enabled = payload.enabled
    db.commit()
    return serialize_model(schedule)


@router.get("/analytics/overview")
def analytics_overview(db: Session = Depends(get_db), _: User | None = Depends(current_user)) -> dict[str, Any]:
    posts = db.execute(select(PlatformPost).order_by(desc(PlatformPost.published_at))).scalars().all()
    metrics = db.execute(select(PostMetricSnapshot).order_by(desc(PostMetricSnapshot.captured_at))).scalars().all()
    account_metrics = db.execute(select(AccountMetricSnapshot).order_by(desc(AccountMetricSnapshot.captured_at))).scalars().all()
    return {
        "posts": [serialize_model(item) for item in posts],
        "post_metrics": [serialize_model(item) for item in metrics],
        "account_metrics": [serialize_model(item) for item in account_metrics],
        "best_topics": best_topics(db),
        "best_hooks": best_hooks(db),
        "follower_growth": [],
        "cross_platform": cross_platform_summary(db),
        "note": "Only officially exposed metrics are stored. Unsupported fields remain null with status codes.",
    }


@router.post("/analytics/demo", dependencies=[Depends(csrf_protected)])
def populate_demo_analytics(db: Session = Depends(get_db), _: User | None = Depends(current_user)) -> dict[str, Any]:
    post = db.execute(select(PlatformPost).where(PlatformPost.status == "simulated")).scalars().first()
    if not post:
        raise HTTPException(409, "Create a simulated publication first")
    raw = {"views": 18400, "likes": 1370, "comments": 94, "shares": 218, "saves": 311, "follows": 86, "completion_rate": 0.64, "retention": 0.71}
    normalized = normalized_post_metrics(raw, followers=25000)
    normalized["performance_score"] = multi_objective_performance({**raw, **normalized, "topic_relevance": 0.9})
    existing = db.execute(
        select(PostMetricSnapshot).where(PostMetricSnapshot.platform_post_id == post.id)
    ).scalars().first()
    if existing:
        return serialize_model(existing)
    snapshot = PostMetricSnapshot(platform_post_id=post.id, metrics=raw, normalized_metrics=normalized, unsupported={"unique_viewers": "simulation_not_available"})
    db.add(snapshot)
    db.commit()
    return serialize_model(snapshot)


@router.get("/experiments")
def experiments(db: Session = Depends(get_db), _: User | None = Depends(current_user)) -> list[dict[str, Any]]:
    return [serialize_model(item) for item in db.execute(select(Experiment).order_by(desc(Experiment.created_at))).scalars()]


@router.post("/experiments", dependencies=[Depends(csrf_protected)])
def create_experiment(payload: ExperimentRequest, db: Session = Depends(get_db), _: User | None = Depends(current_user)) -> dict[str, Any]:
    experiment = Experiment(**payload.model_dump(), status="draft")
    db.add(experiment)
    db.commit()
    return serialize_model(experiment)


@router.get("/providers")
def providers(db: Session = Depends(get_db), _: User | None = Depends(current_user)) -> list[dict[str, Any]]:
    return [serialize_model(item) for item in db.execute(select(ProviderConfiguration)).scalars()]


@router.post("/providers", dependencies=[Depends(csrf_protected)])
def save_provider(payload: ProviderConfigRequest, db: Session = Depends(get_db), _: User | None = Depends(current_user)) -> dict[str, Any]:
    provider = db.execute(select(ProviderConfiguration).where(ProviderConfiguration.provider_type == payload.provider_type, ProviderConfiguration.provider_name == payload.provider_name)).scalar_one_or_none()
    if not provider:
        provider = ProviderConfiguration(provider_type=payload.provider_type, provider_name=payload.provider_name)
        db.add(provider)
    provider.enabled = payload.enabled
    provider.configuration = payload.configuration
    provider.encrypted_secret = SecretBox().encrypt(payload.secret) if payload.secret else provider.encrypted_secret
    provider.health_status = "configured" if payload.enabled else "disabled"
    db.commit()
    return serialize_model(provider)


@router.get("/notifications")
def notifications(db: Session = Depends(get_db), _: User | None = Depends(current_user)) -> list[dict[str, Any]]:
    return [serialize_model(item) for item in db.execute(select(Notification).order_by(desc(Notification.created_at)).limit(100)).scalars()]


@router.get("/audit-events")
def audit_events(db: Session = Depends(get_db), _: User | None = Depends(current_user)) -> list[dict[str, Any]]:
    return [serialize_model(item) for item in db.execute(select(AuditEvent).order_by(desc(AuditEvent.created_at)).limit(200)).scalars()]


@router.get("/errors")
def errors(db: Session = Depends(get_db), _: User | None = Depends(current_user)) -> list[dict[str, Any]]:
    return [serialize_model(item) for item in db.execute(select(ErrorEvent).order_by(desc(ErrorEvent.created_at)).limit(200)).scalars()]


@router.post("/system/pause", dependencies=[Depends(csrf_protected)])
def pause(db: Session = Depends(get_db), user: User | None = Depends(current_user)) -> dict[str, bool]:
    set_global_pause(db, True)
    record_audit(db, "automation.paused", actor_id=user.id if user else None)
    db.commit()
    return {"paused": True}


@router.post("/system/resume", dependencies=[Depends(csrf_protected)])
def resume(db: Session = Depends(get_db), user: User | None = Depends(current_user)) -> dict[str, bool]:
    set_global_pause(db, False)
    record_audit(db, "automation.resumed", actor_id=user.id if user else None)
    db.commit()
    return {"paused": False}


@router.get("/security/status")
def security_status(db: Session = Depends(get_db), _: User | None = Depends(current_user)) -> dict[str, Any]:
    return {
        "localhost_binding": settings.host in {"127.0.0.1", "localhost", "::1"},
        "authentication_required": settings.auth_required,
        "cookie_secure": settings.cookie_secure,
        "encrypted_oauth_credentials": bool(db.scalar(select(func.count(OAuthCredential.id)))) or True,
        "key_storage": "macOS Keychain when available, chmod 600 local fallback otherwise",
        "csrf_protection": True,
        "content_security_policy": True,
        "source_content_treated_as_untrusted": True,
        "prompt_injection_isolation": True,
        "global_pause": get_global_pause(db),
    }


@router.post("/backup", dependencies=[Depends(csrf_protected)])
def backup(db: Session = Depends(get_db), _: User | None = Depends(current_user)) -> dict[str, Any]:
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    archive = storage.root / "backups" / f"socialmediapost-{timestamp}.tar.gz"
    archive.parent.mkdir(parents=True, exist_ok=True)
    with tarfile.open(archive, "w:gz") as tar:
        if settings.database_url.startswith("sqlite"):
            db_path = Path(settings.database_url.replace("sqlite:///", ""))
            if db_path.exists():
                tar.add(db_path, arcname="database/app.db")
        for relative in ["generated", "trends", "analytics", "experiments", "reports"]:
            target = storage.root / relative
            if target.exists():
                tar.add(target, arcname=f"storage/{relative}")
    record_audit(db, "backup.created", resource_type="backup", resource_id=archive.name)
    db.commit()
    return {"created": True, "path": str(archive), "size_bytes": archive.stat().st_size}


@router.get("/reports/{report_name}.{format}")
def report(report_name: str, format: str, db: Session = Depends(get_db), _: User | None = Depends(current_user)) -> StreamingResponse:
    data = report_data(report_name, db)
    if format == "csv":
        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=sorted(data[0].keys()) if data else ["status"])
        writer.writeheader()
        writer.writerows(data or [{"status": "no_data"}])
        return StreamingResponse(iter([output.getvalue()]), media_type="text/csv", headers={"Content-Disposition": f"attachment; filename={report_name}.csv"})
    if format == "pdf":
        buffer = io.BytesIO()
        pdf = canvas.Canvas(buffer, pagesize=letter)
        pdf.setTitle(report_name)
        y = 750
        pdf.drawString(50, y, report_name.replace("_", " ").title())
        y -= 30
        for row in data[:40]:
            text = json.dumps(row, default=str)[:110]
            pdf.drawString(50, y, text)
            y -= 16
            if y < 50:
                pdf.showPage()
                y = 750
        pdf.save()
        buffer.seek(0)
        return StreamingResponse(buffer, media_type="application/pdf", headers={"Content-Disposition": f"attachment; filename={report_name}.pdf"})
    raise HTTPException(400, "Format must be csv or pdf")


def set_session(response: Response, user_id: str) -> None:
    response.set_cookie(SESSION_COOKIE, SessionSigner().issue(user_id), httponly=True, secure=settings.cookie_secure, samesite="strict", max_age=settings.session_ttl_minutes * 60)
    response.set_cookie(CSRF_COOKIE, generate_csrf_token(), httponly=False, secure=settings.cookie_secure, samesite="strict", max_age=settings.session_ttl_minutes * 60)


def seed_defaults(db: Session) -> None:
    if not db.execute(select(Schedule)).scalars().first():
        db.add_all([
            Schedule(name="trend_discovery", workflow_type="trend_discovery", cron_expression=settings.trend_discovery_cron, timezone=settings.timezone, enabled=True),
            Schedule(name="content_production", workflow_type="content_production", cron_expression=settings.content_workflow_cron, timezone=settings.timezone, enabled=True),
        ])
    if not db.execute(select(ProviderConfiguration)).scalars().first():
        providers = {
            "llm": settings.llm_provider,
            "tts": settings.tts_provider,
            "stt": settings.stt_provider,
            "image": settings.image_provider,
            "video": settings.video_provider,
            "moderation": settings.moderation_provider,
            "embeddings": settings.embeddings_provider,
        }
        db.add_all([ProviderConfiguration(provider_type=kind, provider_name=name, enabled=name not in {"disabled", ""}, health_status="configured" if name not in {"disabled", ""} else "disabled") for kind, name in providers.items()])


def get_global_pause(db: Session) -> bool:
    setting = db.execute(select(SystemSetting).where(SystemSetting.key == "global_pause")).scalar_one_or_none()
    return bool(setting.value) if setting else settings.global_pause


def set_global_pause(db: Session, value: bool) -> None:
    setting = db.execute(select(SystemSetting).where(SystemSetting.key == "global_pause")).scalar_one_or_none()
    if not setting:
        setting = SystemSetting(key="global_pause", value=value)
        db.add(setting)
    else:
        setting.value = value
        setting.version += 1


def internet_status() -> str:
    import socket
    try:
        socket.create_connection(("1.1.1.1", 53), timeout=0.5).close()
        return "online"
    except OSError:
        return "offline"


def next_schedule(db: Session) -> dict[str, Any] | None:
    schedule = db.execute(select(Schedule).where(Schedule.enabled.is_(True)).order_by(Schedule.name)).scalars().first()
    return serialize_model(schedule) if schedule else None


def best_topics(db: Session) -> list[dict[str, Any]]:
    rows = db.execute(select(SourceVideo.topic, func.count(ContentPackage.id)).join(TrendCandidate, TrendCandidate.source_video_id == SourceVideo.id).join(ContentConcept, ContentConcept.trend_candidate_id == TrendCandidate.id).join(ContentPackage, ContentPackage.concept_id == ContentConcept.id).group_by(SourceVideo.topic)).all()
    return [{"topic": topic or "unknown", "packages": count} for topic, count in rows]


def best_hooks(db: Session) -> list[dict[str, Any]]:
    variants = db.execute(select(PlatformVariant).limit(20)).scalars().all()
    return [{"hook": item.metadata_json.get("hook"), "platform": item.platform} for item in variants if item.metadata_json.get("hook")]


def cross_platform_summary(db: Session) -> list[dict[str, Any]]:
    rows = db.execute(select(PlatformVariant.platform, func.count(PlatformVariant.id)).group_by(PlatformVariant.platform)).all()
    return [{"platform": platform, "content_count": count} for platform, count in rows]


def report_data(report_name: str, db: Session) -> list[dict[str, Any]]:
    if report_name in {"daily_trends", "best_performing_topics"}:
        return list_trends(db, None)[:100]
    if report_name in {"daily_content", "publication_summary", "platform_comparison"}:
        return list_packages(db, None)[:100]
    if report_name in {"weekly_experiments"}:
        return experiments(db, None)
    if report_name in {"api_usage_cost"}:
        return [{"provider": item.provider_name, "type": item.provider_type, "enabled": item.enabled, "estimated_cost_usd": 0} for item in db.execute(select(ProviderConfiguration)).scalars()]
    return [{"report": report_name, "generated_at": datetime.now(UTC), "status": "available"}]
