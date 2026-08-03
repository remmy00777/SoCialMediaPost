from __future__ import annotations

import math
import statistics
import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.models import (
    BrandProfile,
    Creator,
    OAuthCredential,
    PlatformAccount,
    TrendCandidate,
    TrendScore,
    TrendSource,
    WorkflowRun,
)
from app.platforms.registry import registry
from app.schemas import CreatorDiscoveryRequest, NormalizedVideo
from app.services.audit import record_audit
from app.services.publication import PublicationService
from app.services.workflow import WorkflowService


class CreatorDiscoveryError(RuntimeError):
    pass


class CreatorDiscoveryService:
    def __init__(self, db: Session, settings: Settings | None = None) -> None:
        self.db = db
        self.settings = settings or get_settings()

    def create_run(
        self,
        payload: CreatorDiscoveryRequest,
        user_id: str | None,
    ) -> WorkflowRun:
        run = WorkflowRun(
            workflow_type="creator_discovery",
            status="queued",
            correlation_id=f"creator-discovery-{uuid.uuid4()}",
            summary={
                "request": payload.model_dump(mode="json"),
                "requested_by_user_id": user_id,
            },
        )
        self.db.add(run)
        self.db.commit()
        return run

    def execute(
        self,
        run_id: str,
        payload: CreatorDiscoveryRequest,
        user_id: str | None,
    ) -> dict[str, Any]:
        run = self.db.get(WorkflowRun, run_id)
        if not run:
            raise CreatorDiscoveryError("Creator discovery run was not found")

        run.status = "running"
        run.started_at = datetime.now(UTC)
        run.error_message = None
        self.db.commit()

        query = self._resolved_query(payload)
        platform_results: dict[str, list[dict[str, Any]]] = {}
        errors: list[dict[str, str]] = []

        if payload.platform in {"youtube", "both"}:
            try:
                raw_youtube = registry.get("youtube").discover_creators(
                    query=query,
                    max_creators=payload.top_n,
                    recent_posts_per_creator=payload.recent_posts_per_creator,
                    region=self.settings.youtube_region,
                    language=self._brand_language(),
                )
                platform_results["youtube"] = self._rank(raw_youtube, "youtube")[
                    : payload.top_n
                ]
            except Exception as exc:
                errors.append({"platform": "youtube", "error": str(exc)[:1000]})

        if payload.platform in {"instagram", "both"}:
            try:
                ig_user_id, access_token = self._instagram_context()
                hashtags = payload.hashtags or self._hashtags_from_query(query)
                raw_instagram = registry.get("instagram").discover_creators(
                    ig_user_id=ig_user_id,
                    access_token=access_token,
                    hashtags=hashtags,
                    usernames=payload.instagram_usernames,
                    max_creators=payload.top_n,
                    recent_posts_per_creator=payload.recent_posts_per_creator,
                )
                platform_results["instagram"] = self._rank(
                    raw_instagram,
                    "instagram",
                )[: payload.top_n]
            except Exception as exc:
                errors.append({"platform": "instagram", "error": str(exc)[:1000]})

        creator_ids: list[str] = []
        candidate_ids: list[str] = []
        platform_counts: dict[str, int] = {}

        for platform, creators in platform_results.items():
            platform_counts[platform] = len(creators)
            for creator_data in creators:
                creator = self._upsert_creator(
                    creator_data,
                    query=query,
                    run_id=run.id,
                )
                creator_ids.append(creator.id)
                if payload.import_latest_as_trends and creator_data.get("latest_content"):
                    candidate_id = self._prepare_latest(
                        creator,
                        creator_data,
                        run,
                    )
                    if candidate_id:
                        candidate_ids.append(candidate_id)

        succeeded = bool(creator_ids)
        run.status = "succeeded" if succeeded else "failed"
        run.finished_at = datetime.now(UTC)
        run.error_message = None if succeeded else (
            "; ".join(item["error"] for item in errors)[:2000]
            or "No creators were returned by the configured official APIs"
        )
        run.summary = {
            "request": payload.model_dump(mode="json"),
            "requested_by_user_id": user_id,
            "query": query,
            "platform_counts": platform_counts,
            "creator_count": len(creator_ids),
            "latest_content_candidates": len(candidate_ids),
            "creator_ids": creator_ids,
            "candidate_ids": candidate_ids,
            "errors": errors,
            "limitations": {
                "youtube": (
                    "Results are channels matching the search query, ranked by this "
                    "application's transparent recent-performance score."
                ),
                "instagram": (
                    "Official discovery is limited to professional accounts found through "
                    "supplied usernames or permitted hashtag media. Other-creators' view "
                    "counts are not exposed."
                ),
                "media": (
                    "Platform links and metadata are prepared for analysis. Full video "
                    "editing still requires an authorized source file or allowlisted "
                    "delivery host."
                ),
            },
        }
        record_audit(
            self.db,
            "creator_discovery.completed",
            resource_type="workflow_run",
            resource_id=run.id,
            actor_id=user_id,
            correlation_id=run.correlation_id,
            event_data={
                "platform_counts": platform_counts,
                "candidate_count": len(candidate_ids),
                "errors": errors,
            },
        )
        self.db.commit()
        return {
            "run_id": run.id,
            "status": run.status,
            **run.summary,
            "error_message": run.error_message,
        }

    def refresh_latest_search(self) -> dict[str, Any]:
        previous = self.db.execute(
            select(WorkflowRun)
            .where(
                WorkflowRun.workflow_type == "creator_discovery",
                WorkflowRun.status == "succeeded",
            )
            .order_by(desc(WorkflowRun.started_at))
        ).scalars().first()
        if not previous:
            return {"status": "skipped", "reason": "no_previous_creator_discovery"}
        request_data = (previous.summary or {}).get("request")
        if not request_data:
            return {"status": "skipped", "reason": "previous_request_missing"}
        payload = CreatorDiscoveryRequest.model_validate(request_data)
        user_id = (previous.summary or {}).get("requested_by_user_id")
        run = self.create_run(payload, user_id)
        return self.execute(run.id, payload, user_id)

    def prepare_creator_latest(
        self,
        creator_id: str,
        user_id: str | None,
    ) -> dict[str, Any]:
        creator = self.db.get(Creator, creator_id)
        if not creator or creator.deleted_at is not None:
            raise CreatorDiscoveryError("Creator was not found")
        data = dict(creator.raw_data or {})
        if not data.get("latest_content"):
            raise CreatorDiscoveryError("Creator has no recent content available")
        run = WorkflowRun(
            workflow_type="creator_latest_prepare",
            status="running",
            correlation_id=f"creator-latest-{uuid.uuid4()}",
            summary={"creator_id": creator.id},
        )
        self.db.add(run)
        self.db.flush()
        candidate_id = self._prepare_latest(creator, data, run)
        run.status = "succeeded"
        run.finished_at = datetime.now(UTC)
        run.summary = {
            "creator_id": creator.id,
            "candidate_id": candidate_id,
        }
        record_audit(
            self.db,
            "creator_latest.prepared",
            resource_type="creator",
            resource_id=creator.id,
            actor_id=user_id,
            correlation_id=run.correlation_id,
            event_data={"candidate_id": candidate_id},
        )
        self.db.commit()
        return {
            "creator_id": creator.id,
            "candidate_id": candidate_id,
            "status": "ready_for_analysis",
        }

    def discover_single_instagram_creator(
        self,
        username: str,
        recent_posts: int = 5,
    ) -> dict[str, Any]:
        ig_user_id, access_token = self._instagram_context()
        creators = registry.get("instagram").discover_creators(
            ig_user_id=ig_user_id,
            access_token=access_token,
            hashtags=[],
            usernames=[username],
            max_creators=1,
            recent_posts_per_creator=min(max(recent_posts, 1), 10),
        )
        if not creators:
            raise CreatorDiscoveryError(
                "Instagram professional creator was not found or Business Discovery "
                "is unavailable"
            )
        return creators[0]

    def _instagram_context(self) -> tuple[str, str]:
        account = self.db.execute(
            select(PlatformAccount).where(
                PlatformAccount.platform == "instagram",
                PlatformAccount.authorization_status == "connected",
                PlatformAccount.deleted_at.is_(None),
            )
        ).scalars().first()
        if not account:
            raise CreatorDiscoveryError(
                "Connect an Instagram Professional account before running Instagram "
                "discovery"
            )
        credential = self.db.execute(
            select(OAuthCredential).where(
                OAuthCredential.platform_account_id == account.id
            )
        ).scalar_one_or_none()
        if not credential or not credential.encrypted_access_token:
            raise CreatorDiscoveryError("Instagram OAuth credential is unavailable")

        adapter = registry.get("instagram")
        user_access_token = PublicationService(
            self.db,
            self.settings,
        )._fresh_token(adapter, account, credential)
        raw_profile = account.raw_profile or {}
        instagram_profile = raw_profile.get("instagram_business_account") or {}
        ig_user_id = str(
            instagram_profile.get("id")
            or account.external_account_id
            or ""
        )
        if not ig_user_id:
            raise CreatorDiscoveryError(
                "Connected Instagram Professional account ID is unavailable"
            )
        page_id = str(
            raw_profile.get("page_id")
            or raw_profile.get("id")
            or ""
        ) or None
        page_access_token = adapter._page_access_token(
            user_access_token,
            page_id,
        )
        return ig_user_id, page_access_token

    def _upsert_creator(
        self,
        data: dict[str, Any],
        *,
        query: str,
        run_id: str,
    ) -> Creator:
        platform = str(data["platform"])
        external_id = str(data["external_creator_id"])
        creator = self.db.execute(
            select(Creator).where(
                Creator.platform == platform,
                Creator.external_creator_id == external_id,
            )
        ).scalar_one_or_none()
        if not creator:
            creator = Creator(
                platform=platform,
                external_creator_id=external_id,
            )
            self.db.add(creator)
        creator.name = data.get("name") or data.get("username")
        creator.follower_count = data.get("follower_count")
        creator.raw_data = {
            **data,
            "discovery_type": "top_creator",
            "discovery_query": query,
            "discovery_run_id": run_id,
            "discovered_at": datetime.now(UTC).isoformat(),
        }
        self.db.flush()
        return creator

    def _prepare_latest(
        self,
        creator: Creator,
        data: dict[str, Any],
        run: WorkflowRun,
    ) -> str | None:
        latest = data.get("latest_content")
        if not latest:
            return None
        video = NormalizedVideo.model_validate(latest)
        video.data_source = f"{video.platform}_creator_discovery_latest"
        workflow = WorkflowService(self.db, self.settings)
        source = workflow._upsert_source_video(video)
        trend_source = self.db.execute(
            select(TrendSource).where(
                TrendSource.platform == video.platform,
                TrendSource.source_type == video.data_source,
            )
        ).scalar_one_or_none()
        if not trend_source:
            trend_source = TrendSource(
                platform=video.platform,
                source_type=video.data_source,
                label=f"{video.platform.title()} Top Creator Latest Content",
                active=True,
                limitations=(
                    "Metadata and canonical link were collected through an official "
                    "platform API. Full source media is not downloaded from the platform."
                ),
                configuration={},
            )
            self.db.add(trend_source)
            self.db.flush()

        candidate = self.db.execute(
            select(TrendCandidate).where(
                TrendCandidate.source_video_id == source.id,
                TrendCandidate.trend_source_id == trend_source.id,
                TrendCandidate.deleted_at.is_(None),
            )
        ).scalar_one_or_none()
        if not candidate:
            candidate = TrendCandidate(
                source_video_id=source.id,
                trend_source_id=trend_source.id,
                workflow_run_id=run.id,
                rank=int(data.get("rank") or 0) or None,
                selected=True,
                dedupe_group=(
                    f"creator-discovery:{video.platform}:{video.external_video_id}"
                ),
            )
            self.db.add(candidate)
            self.db.flush()
        else:
            candidate.selected = True
            candidate.workflow_run_id = run.id
            candidate.rank = int(data.get("rank") or 0) or candidate.rank

        score_result = workflow.scorer.score(video)
        score = self.db.execute(
            select(TrendScore).where(
                TrendScore.trend_candidate_id == candidate.id
            )
        ).scalar_one_or_none()
        if not score:
            score = TrendScore(
                trend_candidate_id=candidate.id,
                **score_result.model_dump(),
            )
            self.db.add(score)
        else:
            for key, value in score_result.model_dump().items():
                setattr(score, key, value)

        creator_data = dict(creator.raw_data or {})
        creator_data["latest_candidate_id"] = candidate.id
        creator.raw_data = creator_data
        self.db.flush()
        return candidate.id

    def _rank(
        self,
        creators: list[dict[str, Any]],
        platform: str,
    ) -> list[dict[str, Any]]:
        if not creators:
            return []

        enriched: list[dict[str, Any]] = []
        for item in creators:
            data = dict(item)
            posts = list(data.get("recent_posts") or [])
            view_values = [
                int((post.get("metrics") or {}).get("views") or 0)
                for post in posts
                if (post.get("metrics") or {}).get("views") is not None
            ]
            engagement_values = [
                int((post.get("metrics") or {}).get("likes") or 0)
                + int((post.get("metrics") or {}).get("comments") or 0)
                for post in posts
            ]
            follower_count = int(data.get("follower_count") or 0)
            rates: list[float] = []
            for post in posts:
                metrics = post.get("metrics") or {}
                views = int(metrics.get("views") or 0)
                engagement = int(metrics.get("likes") or 0) + int(
                    metrics.get("comments") or 0
                )
                denominator = views if views else follower_count
                if denominator:
                    rates.append(engagement / denominator)

            latest = data.get("latest_content") or (posts[0] if posts else None)
            freshness = self._freshness(latest)
            median_views = statistics.median(view_values) if view_values else 0.0
            median_engagement = (
                statistics.median(engagement_values)
                if engagement_values
                else 0.0
            )
            median_rate = statistics.median(rates) if rates else 0.0
            breakout_count = 0
            for post in posts:
                metrics = post.get("metrics") or {}
                views = int(metrics.get("views") or 0)
                engagement = int(metrics.get("likes") or 0) + int(
                    metrics.get("comments") or 0
                )
                if platform == "youtube" and views >= 1_000_000:
                    breakout_count += 1
                elif platform == "instagram" and engagement >= 100_000:
                    breakout_count += 1
            data.update(
                {
                    "recent_median_views": float(median_views),
                    "recent_median_engagement": float(median_engagement),
                    "recent_engagement_rate": float(median_rate),
                    "breakout_post_count": breakout_count,
                    "freshness": freshness,
                    "latest_content": latest,
                }
            )
            enriched.append(data)

        maxima = {
            "followers": max(int(item.get("follower_count") or 0) for item in enriched),
            "total_views": max(int(item.get("total_views") or 0) for item in enriched),
            "recent_views": max(float(item.get("recent_median_views") or 0) for item in enriched),
            "engagement": max(float(item.get("recent_median_engagement") or 0) for item in enriched),
            "rate": max(float(item.get("recent_engagement_rate") or 0) for item in enriched),
            "breakout": max(int(item.get("breakout_post_count") or 0) for item in enriched),
        }

        weights = (
            {
                "followers": 0.20,
                "total_views": 0.15,
                "recent_views": 0.30,
                "engagement": 0.10,
                "rate": 0.10,
                "breakout": 0.05,
                "freshness": 0.10,
            }
            if platform == "youtube"
            else {
                "followers": 0.35,
                "engagement": 0.30,
                "rate": 0.20,
                "breakout": 0.05,
                "freshness": 0.10,
            }
        )

        for item in enriched:
            raw_components = {
                "followers": self._log_score(
                    int(item.get("follower_count") or 0),
                    maxima["followers"],
                ),
                "total_views": self._log_score(
                    int(item.get("total_views") or 0),
                    maxima["total_views"],
                ),
                "recent_views": self._log_score(
                    float(item.get("recent_median_views") or 0),
                    maxima["recent_views"],
                ),
                "engagement": self._log_score(
                    float(item.get("recent_median_engagement") or 0),
                    maxima["engagement"],
                ),
                "rate": (
                    float(item.get("recent_engagement_rate") or 0)
                    / maxima["rate"]
                    if maxima["rate"]
                    else 0.0
                ),
                "breakout": (
                    int(item.get("breakout_post_count") or 0)
                    / maxima["breakout"]
                    if maxima["breakout"]
                    else 0.0
                ),
                "freshness": float(item.get("freshness") or 0),
            }
            score = sum(
                raw_components[name] * weight
                for name, weight in weights.items()
            ) * 100
            item["creator_score"] = round(score, 2)
            item["score_components"] = {
                name: round(raw_components[name] * 100, 2)
                for name in weights
            }
            item["missing_metrics"] = (
                ["other_creator_video_views"]
                if platform == "instagram"
                else []
            )

        enriched.sort(
            key=lambda item: (
                float(item.get("creator_score") or 0),
                int(item.get("follower_count") or 0),
            ),
            reverse=True,
        )
        for rank, item in enumerate(enriched, 1):
            item["rank"] = rank
        return enriched

    def _resolved_query(self, payload: CreatorDiscoveryRequest) -> str:
        if payload.query and payload.query.strip():
            return payload.query.strip()
        profile = self.db.execute(
            select(BrandProfile).order_by(desc(BrandProfile.created_at))
        ).scalars().first()
        return (
            profile.niche
            if profile and profile.niche
            else "popular creators"
        ).strip()

    def _brand_language(self) -> str | None:
        profile = self.db.execute(
            select(BrandProfile).order_by(desc(BrandProfile.created_at))
        ).scalars().first()
        return profile.languages[0] if profile and profile.languages else None

    @staticmethod
    def _hashtags_from_query(query: str) -> list[str]:
        tokens = [
            "".join(
                character
                for character in token.lower()
                if character.isalnum()
            )
            for token in query.split()
        ]
        result = [token for token in tokens if token]
        for fallback in ("viral", "reels", "trending", "explorepage"):
            if fallback not in result:
                result.append(fallback)
        return result[:10]

    @staticmethod
    def _freshness(latest: dict[str, Any] | None) -> float:
        if not latest or not latest.get("published_at"):
            return 0.0
        try:
            published = datetime.fromisoformat(
                str(latest["published_at"]).replace("Z", "+00:00")
            )
            if published.tzinfo is None:
                published = published.replace(tzinfo=UTC)
            age_days = max(
                (
                    datetime.now(UTC)
                    - published.astimezone(UTC)
                ).total_seconds()
                / 86400,
                0,
            )
            return math.exp(-age_days / 30)
        except (TypeError, ValueError):
            return 0.0

    @staticmethod
    def _log_score(value: float, maximum: float) -> float:
        if value <= 0 or maximum <= 0:
            return 0.0
        return math.log1p(value) / math.log1p(maximum)
