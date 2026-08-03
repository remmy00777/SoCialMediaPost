from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.models import TrendCandidate, TrendScore, TrendSource
from app.schemas import NormalizedVideo
from app.platforms.registry import registry
from app.services.authorized_media import AuthorizedMediaService
from app.services.creator_discovery import CreatorDiscoveryService
from app.services.workflow import WorkflowService


class CreatorWatchError(RuntimeError):
    pass


class CreatorWatchService:
    def __init__(self, db: Session, settings: Settings | None = None) -> None:
        self.db = db
        self.settings = settings or get_settings()

    def check_watch(self, watch_id: str) -> dict[str, Any]:
        watch = self.db.get(TrendSource, watch_id)
        if not watch or watch.deleted_at is not None or watch.source_type != "creator_watch":
            raise CreatorWatchError("Creator watch was not found")
        if not watch.active:
            raise CreatorWatchError("Creator watch is disabled")

        configuration = dict(watch.configuration or {})
        platform = watch.platform
        creator_id = str(configuration.get("external_creator_id") or "").strip()
        if not creator_id:
            raise CreatorWatchError("Creator identifier is required")

        if platform == "youtube":
            uploads = registry.get("youtube").list_creator_uploads(
                creator_id,
                limit=5,
            )
        elif platform == "instagram":
            creator = CreatorDiscoveryService(
                self.db,
                self.settings,
            ).discover_single_instagram_creator(
                creator_id,
                recent_posts=5,
            )
            uploads = [
                NormalizedVideo.model_validate(item)
                for item in creator.get("recent_posts", [])
            ]
        else:
            configuration["last_checked_at"] = datetime.now(UTC).isoformat()
            configuration["last_check_status"] = (
                "requires_authorized_creator_connection_or_licensed_feed"
            )
            watch.configuration = configuration
            self.db.commit()
            return {
                "watch_id": watch.id,
                "platform": platform,
                "status": configuration["last_check_status"],
                "new_candidates": [],
                "prepared_packages": [],
            }
        workflow = WorkflowService(self.db, self.settings)
        capture = AuthorizedMediaService(self.db, self.settings)
        new_candidates: list[str] = []
        prepared_packages: list[str] = []
        errors: list[dict[str, str]] = []

        for video in reversed(uploads):
            source = workflow._upsert_source_video(video)
            existing = self.db.execute(
                select(TrendCandidate).where(
                    TrendCandidate.source_video_id == source.id,
                    TrendCandidate.trend_source_id == watch.id,
                    TrendCandidate.deleted_at.is_(None),
                )
            ).scalar_one_or_none()
            if existing:
                continue

            candidate = TrendCandidate(
                source_video_id=source.id,
                trend_source_id=watch.id,
                selected=True,
                dedupe_group=f"creator-watch:{platform}:{video.external_video_id}",
            )
            self.db.add(candidate)
            self.db.flush()
            score = workflow.scorer.score(video)
            self.db.add(TrendScore(trend_candidate_id=candidate.id, **score.model_dump()))
            self.db.commit()
            new_candidates.append(candidate.id)

            if not configuration.get("auto_capture_and_prepare"):
                continue
            template = str(configuration.get("authorized_media_url_template") or "").strip()
            if not template:
                errors.append({"candidate_id": candidate.id, "error": "Authorized media URL template is missing"})
                continue

            try:
                source_url = template.format(
                    external_video_id=video.external_video_id,
                    creator_id=creator_id,
                    platform=platform,
                )
                capture.capture_for_candidate(
                    candidate.id,
                    source_url=source_url,
                    rights_status=str(configuration.get("rights_status") or ""),
                    rights_owner=str(configuration.get("rights_owner") or ""),
                    license_reference=configuration.get("license_reference"),
                    attribution_text=configuration.get("attribution_text"),
                    allow_full_reuse=bool(configuration.get("allow_full_reuse")),
                    user_id=configuration.get("user_id"),
                )
                package = WorkflowService(self.db, self.settings).run_candidate_remix(candidate.id)
                prepared_packages.append(package.id)
            except Exception as exc:
                errors.append({"candidate_id": candidate.id, "error": str(exc)[:500]})

        configuration["last_checked_at"] = datetime.now(UTC).isoformat()
        configuration["last_check_status"] = "completed"
        if uploads:
            configuration["last_seen_post_id"] = uploads[0].external_video_id
        watch.configuration = configuration
        self.db.commit()
        return {
            "watch_id": watch.id,
            "platform": platform,
            "status": "completed",
            "new_candidates": new_candidates,
            "prepared_packages": prepared_packages,
            "errors": errors,
        }

    def check_all(self) -> list[dict[str, Any]]:
        watches = self.db.execute(
            select(TrendSource).where(
                TrendSource.source_type == "creator_watch",
                TrendSource.active.is_(True),
                TrendSource.deleted_at.is_(None),
            )
        ).scalars().all()
        results: list[dict[str, Any]] = []
        for watch in watches:
            try:
                results.append(self.check_watch(watch.id))
            except Exception as exc:
                results.append({
                    "watch_id": watch.id,
                    "platform": watch.platform,
                    "status": "failed",
                    "error": str(exc)[:500],
                })
        return results
