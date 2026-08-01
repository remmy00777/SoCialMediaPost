from __future__ import annotations

import hashlib
import json
import logging
import shutil
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.models import (
    BrandProfile,
    ContentConcept,
    ContentPackage,
    GeneratedAsset,
    OriginalityCheck,
    PlatformVariant,
    PolicyCheck,
    PlatformAccount,
    PublicationJob,
    SourceMetric,
    SourceVideo,
    TaskRun,
    TrendAnalysis,
    TrendCandidate,
    TrendScore,
    TrendSource,
    WorkflowRun,
)
from app.platforms.registry import registry
from app.schemas import NormalizedVideo
from app.services.audit import record_audit
from app.services.content_generator import BrandContext, LocalTemplateProvider
from app.services.media import MediaRenderer
from app.services.notifications import NotificationService
from app.services.originality import originality_report
from app.services.policy import policy_report
from app.services.storage import StorageManager
from app.services.trend_scoring import TrendScorer, dedupe_key


logger = logging.getLogger(__name__)


class WorkflowService:
    def __init__(self, db: Session, settings: Settings | None = None) -> None:
        self.db = db
        self.settings = settings or get_settings()
        self.storage = StorageManager(self.settings)
        self.scorer = TrendScorer()
        self.generator = LocalTemplateProvider()
        self.renderer = MediaRenderer(self.storage)
        self.notifications = NotificationService(self.settings)

    def run_trend_discovery(self, max_candidates: int = 30, select_limit: int = 10) -> WorkflowRun:
        run = self._start_run("trend_discovery")
        try:
            videos: list[NormalizedVideo] = []
            for adapter in registry.all():
                if self._platform_enabled(adapter.platform):
                    try:
                        videos.extend(adapter.discover_trends(limit=max_candidates))
                    except Exception as exc:  # isolated platform failure
                        logger.warning(
                            "Trend discovery failed for one platform",
                            extra={"context": {"platform": adapter.platform, "error": str(exc)}},
                        )
            if not videos and self.settings.demo_mode:
                videos = self._load_demo_trends()
            candidates: list[tuple[TrendCandidate, TrendScore]] = []
            for video in videos[:max_candidates]:
                task = self._start_task(run, "normalize_and_score", f"{video.platform}:{video.external_video_id}")
                try:
                    source = self._upsert_source_video(video)
                    source_record = self._get_or_create_trend_source(video)
                    candidate = TrendCandidate(
                        source_video_id=source.id,
                        trend_source_id=source_record.id,
                        workflow_run_id=run.id,
                        dedupe_group=dedupe_key(video),
                    )
                    self.db.add(candidate)
                    self.db.flush()
                    score_result = self.scorer.score(video)
                    score = TrendScore(
                        trend_candidate_id=candidate.id,
                        score=score_result.score,
                        confidence=score_result.confidence,
                        components=score_result.components,
                        explanation=score_result.explanation,
                        missing_metrics=score_result.missing_metrics,
                    )
                    self.db.add(score)
                    self._finish_task(task, "succeeded", {"score": score_result.score})
                    candidates.append((candidate, score))
                except Exception as exc:
                    self._finish_task(task, "failed", error=str(exc))
            seen: set[str] = set()
            selected = 0
            for rank, (candidate, score) in enumerate(sorted(candidates, key=lambda pair: pair[1].score, reverse=True), 1):
                candidate.rank = rank
                if candidate.dedupe_group not in seen and selected < select_limit:
                    candidate.selected = True
                    seen.add(candidate.dedupe_group or candidate.id)
                    selected += 1
            run.status = "succeeded"
            run.finished_at = datetime.now(UTC)
            run.summary = {
                "candidates": len(candidates),
                "selected": selected,
                "sources": sorted({video.data_source for video in videos}),
                "demo": all(video.data_source == "demonstration_fixture" for video in videos) if videos else False,
            }
            record_audit(self.db, "workflow.trend_discovery.completed", resource_type="workflow_run", resource_id=run.id, correlation_id=run.correlation_id, event_data=run.summary)
            self.db.commit()
            self.notifications.send_macos("Trend discovery completed", f"Selected {selected} trend opportunities.")
            return run
        except Exception as exc:
            self._fail_run(run, exc)
            raise

    def run_content_workflow(self, max_items: int = 10) -> WorkflowRun:
        run = self._start_run("content_production")
        if self._is_paused():
            run.status = "skipped"
            run.finished_at = datetime.now(UTC)
            run.summary = {"reason": "global_pause"}
            self.db.commit()
            return run
        candidates = self.db.execute(
            select(TrendCandidate)
            .where(TrendCandidate.selected.is_(True), TrendCandidate.deleted_at.is_(None))
            .order_by(desc(TrendCandidate.created_at))
            .limit(max_items)
        ).scalars().all()
        generated = 0
        failed = 0
        auto_queued = 0
        per_platform_queued = {"tiktok": 0, "instagram": 0, "youtube": 0}
        for candidate in candidates:
            task = self._start_task(run, "generate_content_package", candidate.id)
            try:
                package = self._generate_for_candidate(candidate, run)
                queued = self._queue_auto_publications(package, per_platform_queued)
                auto_queued += queued
                generated += 1
                self._finish_task(task, "succeeded", {"platform_variants": 3, "auto_publications_queued": queued})
                self.db.commit()
            except Exception as exc:
                failed += 1
                self.db.rollback()
                task = self.db.get(TaskRun, task.id)
                if task:
                    self._finish_task(task, "failed", error=str(exc))
                    self.db.commit()
                logger.exception("Content generation failed for candidate", extra={"context": {"candidate_id": candidate.id}})
        run = self.db.get(WorkflowRun, run.id) or run
        run.status = "succeeded" if generated else "failed" if failed else "succeeded"
        run.finished_at = datetime.now(UTC)
        run.summary = {"generated_packages": generated, "failed_items": failed, "candidate_count": len(candidates), "auto_publications_queued": auto_queued}
        record_audit(self.db, "workflow.content_production.completed", resource_type="workflow_run", resource_id=run.id, correlation_id=run.correlation_id, event_data=run.summary)
        self.db.commit()
        if generated:
            self.notifications.send_macos("Content ready", f"Generated {generated} cross-platform content packages.")
        return run

    def _generate_for_candidate(self, candidate: TrendCandidate, run: WorkflowRun) -> ContentPackage:
        source = self.db.get(SourceVideo, candidate.source_video_id)
        if not source:
            raise RuntimeError("Source video is missing")
        source_payload = self._source_payload(source)
        analysis_payload = self.generator.analyze_trend(source_payload)
        analysis = self.db.execute(
            select(TrendAnalysis).where(TrendAnalysis.trend_candidate_id == candidate.id)
        ).scalar_one_or_none()
        if not analysis:
            analysis = TrendAnalysis(
                trend_candidate_id=candidate.id,
                observations=analysis_payload["observations"],
                interpretations=analysis_payload["interpretations"],
                confidence=analysis_payload["confidence"],
                supporting_signals=analysis_payload["supporting_signals"],
                missing_information=analysis_payload["missing_information"],
                assumptions=analysis_payload["assumptions"],
            )
            self.db.add(analysis)
            self.db.flush()
        self.storage.atomic_write_json(self.storage.root / "trends" / "analyses" / f"{candidate.id}.json", analysis_payload)
        brand = self._brand_context()
        concept_payloads = self.generator.generate_concepts(source_payload, analysis_payload, brand)
        selected_concept: ContentConcept | None = None
        for payload in concept_payloads:
            concept = ContentConcept(
                trend_candidate_id=candidate.id,
                status="selected" if payload["selected"] else "rejected",
                selected=payload["selected"],
                concept=payload["concept"],
                component_scores=payload["component_scores"],
                total_score=payload["total_score"],
                prompt_version=payload["prompt_version"],
            )
            self.db.add(concept)
            self.db.flush()
            if payload["selected"]:
                selected_concept = concept
        if not selected_concept:
            raise RuntimeError("No concept selected")
        package_payload = self.generator.generate_package(selected_concept.concept, source_payload, brand)
        originality = originality_report(package_payload, source_payload)
        compliance = policy_report(package_payload)
        idempotency_key = hashlib.sha256(f"{candidate.id}:{selected_concept.id}:{self.generator.version}".encode()).hexdigest()
        existing = self.db.execute(
            select(ContentPackage).where(ContentPackage.idempotency_key == idempotency_key)
        ).scalar_one_or_none()
        if existing:
            return existing
        package = ContentPackage(
            concept_id=selected_concept.id,
            status="draft",
            title=package_payload["title"],
            storage_path=str(self.storage.root / "generated"),
            quality_score=0,
            predicted_performance=package_payload["predicted_performance_range"],
            generation_metadata={**package_payload["generation_metadata"], "workflow_run_id": run.id},
            approval_mode=self.settings.approval_mode,
            idempotency_key=idempotency_key,
        )
        self.db.add(package)
        self.db.flush()
        self.db.add(
            OriginalityCheck(
                content_package_id=package.id,
                passed=originality["passed"],
                component_scores=originality["component_scores"],
                thresholds=originality["thresholds"],
                blocking_reasons=originality["blocking_reasons"],
            )
        )
        self.db.add(
            PolicyCheck(
                content_package_id=package.id,
                passed=compliance["passed"],
                checks=compliance["checks"],
                blocking_reasons=compliance["blocking_reasons"],
            )
        )
        brand_profile = self.db.execute(select(BrandProfile).order_by(desc(BrandProfile.created_at))).scalars().first()
        automatic_ready = (
            self.settings.approval_mode == "controlled_auto"
            and self.settings.auto_publish_enabled
            and bool(brand_profile and brand_profile.approved)
        )
        target_status = "ready_to_post" if (
            self.settings.approval_mode == "manual_export" or automatic_ready
        ) and originality["passed"] and compliance["passed"] else "drafts"
        quality_scores: list[float] = []
        for platform in ("tiktok", "instagram", "youtube"):
            adapted = self.generator.adapt_platform(package_payload, platform)
            directory = self.storage.package_dir(platform, target_status, package.id)
            rendered = self.renderer.render_platform_package(
                directory,
                adapted,
                analysis_payload,
                originality,
                compliance,
                platform,
                package.id,
            )
            variant = PlatformVariant(
                content_package_id=package.id,
                platform=platform,
                status="ready_to_post" if target_status == "ready_to_post" else "draft",
                media_path=rendered["final_video"],
                thumbnail_path=rendered["thumbnail"],
                subtitle_path=rendered["subtitles"],
                metadata_json=adapted,
                media_validation=rendered["validation"],
            )
            self.db.add(variant)
            self.db.flush()
            for asset_type, path_value in {
                "video": rendered["final_video"],
                "preview": rendered["preview"],
                "thumbnail": rendered["thumbnail"],
                "subtitles": rendered["subtitles"],
            }.items():
                path = Path(path_value)
                self.db.add(
                    GeneratedAsset(
                        content_package_id=package.id,
                        platform_variant_id=variant.id,
                        asset_type=asset_type,
                        path=str(path),
                        sha256=self.storage.sha256(path),
                        size_bytes=path.stat().st_size,
                        mime_type=self._mime(path),
                        rights_status="original",
                    )
                )
            if target_status == "ready_to_post":
                self.storage.mirror_ready_package(platform, directory, package.id)
            quality_scores.append(rendered["quality_score"])
        package.status = "ready_to_post" if target_status == "ready_to_post" else "review"
        package.quality_score = round(sum(quality_scores) / len(quality_scores), 2)
        package.storage_path = str(self.storage.root / "generated")
        record_audit(
            self.db,
            "content_package.generated",
            resource_type="content_package",
            resource_id=package.id,
            correlation_id=run.correlation_id,
            event_data={"status": package.status, "quality_score": package.quality_score},
        )
        return package

    def _queue_auto_publications(
        self, package: ContentPackage, per_platform_queued: dict[str, int]
    ) -> int:
        if (
            self.settings.approval_mode != "controlled_auto"
            or not self.settings.auto_publish_enabled
            or package.status != "ready_to_post"
            or package.quality_score < 70
        ):
            return 0
        limits = {
            "tiktok": self.settings.tiktok_daily_limit_per_run,
            "instagram": self.settings.instagram_daily_limit_per_run,
            "youtube": self.settings.youtube_daily_limit_per_run,
        }
        queued = 0
        variants = self.db.execute(
            select(PlatformVariant).where(PlatformVariant.content_package_id == package.id)
        ).scalars().all()
        for variant in variants:
            if per_platform_queued.get(variant.platform, 0) >= limits.get(variant.platform, 0):
                continue
            account = self.db.execute(
                select(PlatformAccount).where(
                    PlatformAccount.platform == variant.platform,
                    PlatformAccount.authorization_status == "connected",
                    PlatformAccount.publishing_eligible.is_(True),
                    PlatformAccount.deleted_at.is_(None),
                )
            ).scalars().first()
            if not account:
                continue
            key = f"auto:{variant.id}"
            existing = self.db.execute(
                select(PublicationJob).where(PublicationJob.idempotency_key == key)
            ).scalar_one_or_none()
            if existing:
                continue
            self.db.add(
                PublicationJob(
                    platform_variant_id=variant.id,
                    platform_account_id=account.id,
                    status="queued",
                    idempotency_key=key,
                )
            )
            variant.status = "publishing_queued"
            per_platform_queued[variant.platform] = per_platform_queued.get(variant.platform, 0) + 1
            queued += 1
        return queued

    def _upsert_source_video(self, video: NormalizedVideo) -> SourceVideo:
        source = self.db.execute(
            select(SourceVideo).where(
                SourceVideo.platform == video.platform,
                SourceVideo.external_video_id == video.external_video_id,
            )
        ).scalar_one_or_none()
        values = video.model_dump(exclude={"metrics"}, mode="python")
        values["raw_response"] = video.raw_response
        values["creator_external_id"] = video.creator_external_id
        if source is None:
            source = SourceVideo(**values)
            self.db.add(source)
            self.db.flush()
        else:
            for key, value in values.items():
                setattr(source, key, value)
        metric = SourceMetric(source_video_id=source.id, **video.metrics.model_dump())
        self.db.add(metric)
        self.db.flush()
        self.storage.atomic_write_json(
            self.storage.root / "trends" / "normalized" / f"{video.platform}_{video.external_video_id}.json",
            video.model_dump(mode="json"),
        )
        return source

    def _get_or_create_trend_source(self, video: NormalizedVideo) -> TrendSource:
        source = self.db.execute(
            select(TrendSource).where(
                TrendSource.platform == video.platform,
                TrendSource.source_type == video.data_source,
            )
        ).scalar_one_or_none()
        if source:
            return source
        limitations = {
            "youtube_most_popular_chart": "Official chart, not the former general Trending page.",
            "demonstration_fixture": "Synthetic local fixture, never presented as live platform data.",
            "manual_url_import": "Only user-supplied metadata is available unless an official API can enrich it.",
        }.get(video.data_source, "Availability depends on the configured official or licensed source.")
        source = TrendSource(
            platform=video.platform,
            source_type=video.data_source,
            label=video.data_source.replace("_", " ").title(),
            limitations=limitations,
            configuration={},
        )
        self.db.add(source)
        self.db.flush()
        return source

    def _brand_context(self) -> BrandContext:
        profile = self.db.execute(select(BrandProfile).order_by(desc(BrandProfile.created_at))).scalars().first()
        if not profile:
            profile = BrandProfile(approved=self.settings.demo_mode)
            self.db.add(profile)
            self.db.flush()
        return BrandContext(
            name=profile.name,
            niche=profile.niche,
            target_audience=profile.target_audience,
            brand_voice=profile.brand_voice,
            topics_exclude=profile.topics_exclude,
            preferred_duration_seconds=profile.preferred_duration_seconds,
        )

    def _source_payload(self, source: SourceVideo) -> dict[str, Any]:
        latest_metric = self.db.execute(
            select(SourceMetric)
            .where(SourceMetric.source_video_id == source.id)
            .order_by(desc(SourceMetric.retrieved_at))
        ).scalars().first()
        payload = {
            "platform": source.platform,
            "external_video_id": source.external_video_id,
            "canonical_url": source.canonical_url,
            "creator_name": source.creator_name,
            "creator_follower_count": source.creator_follower_count,
            "title": source.title,
            "caption": source.caption,
            "hashtags": source.hashtags,
            "topic": source.topic,
            "transcript": source.transcript,
            "published_at": source.published_at.isoformat() if source.published_at else None,
            "data_source": source.data_source,
        }
        if latest_metric:
            payload["metrics"] = {
                "views": latest_metric.views,
                "likes": latest_metric.likes,
                "comments": latest_metric.comments,
                "shares": latest_metric.shares,
                "saves": latest_metric.saves,
            }
        return payload

    def _load_demo_trends(self) -> list[NormalizedVideo]:
        locations = [Path("fixtures/trends.json"), Path("../fixtures/trends.json"), Path("/app/fixtures/trends.json")]
        fixture = next((path for path in locations if path.exists()), None)
        if not fixture:
            raise FileNotFoundError("Demo trend fixture not found")
        return [NormalizedVideo.model_validate(item) for item in json.loads(fixture.read_text())]

    def _start_run(self, workflow_type: str) -> WorkflowRun:
        run = WorkflowRun(
            workflow_type=workflow_type,
            status="running",
            correlation_id=f"{workflow_type}-{uuid.uuid4()}",
        )
        self.db.add(run)
        self.db.flush()
        return run

    def _start_task(self, run: WorkflowRun, name: str, item_key: str | None = None) -> TaskRun:
        task = TaskRun(workflow_run_id=run.id, task_name=name, item_key=item_key)
        self.db.add(task)
        self.db.flush()
        return task

    def _finish_task(
        self, task: TaskRun, status: str, result: dict[str, Any] | None = None, error: str | None = None
    ) -> None:
        task.status = status
        task.finished_at = datetime.now(UTC)
        task.result = result or {}
        task.error_message = error

    def _fail_run(self, run: WorkflowRun, error: Exception) -> None:
        run.status = "failed"
        run.finished_at = datetime.now(UTC)
        run.error_message = str(error)
        self.db.commit()

    def _is_paused(self) -> bool:
        from app.models import SystemSetting

        setting = self.db.execute(select(SystemSetting).where(SystemSetting.key == "global_pause")).scalar_one_or_none()
        return bool(setting.value) if setting else self.settings.global_pause

    def _platform_enabled(self, platform: str) -> bool:
        return bool(getattr(self.settings, f"enable_{platform}"))

    @staticmethod
    def _mime(path: Path) -> str:
        return {".mp4": "video/mp4", ".png": "image/png", ".srt": "application/x-subrip"}.get(path.suffix, "application/octet-stream")
