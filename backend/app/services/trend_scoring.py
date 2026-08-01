from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from app.schemas import NormalizedVideo, TrendScoreResult


DEFAULT_WEIGHTS = {
    "recency": 0.14,
    "views": 0.08,
    "view_velocity": 0.18,
    "engagement_ratio": 0.12,
    "engagement_velocity": 0.12,
    "follower_adjusted": 0.08,
    "cross_platform": 0.08,
    "topic_relevance": 0.08,
    "freshness": 0.05,
    "originality_opportunity": 0.04,
    "brand_safety": 0.03,
}


def log_scale(value: float | int | None, cap: float) -> float | None:
    if value is None:
        return None
    return min(math.log1p(max(float(value), 0)) / math.log1p(cap), 1.0)


def bounded(value: float | None, low: float, high: float) -> float | None:
    if value is None:
        return None
    if high <= low:
        return 0.0
    return min(max((value - low) / (high - low), 0.0), 1.0)


class TrendScorer:
    def __init__(self, weights: dict[str, float] | None = None) -> None:
        self.weights = weights or DEFAULT_WEIGHTS

    def score(
        self,
        video: NormalizedVideo,
        *,
        cross_platform_count: int = 1,
        topic_relevance: float = 0.7,
        originality_opportunity: float = 0.7,
        brand_safety: float = 1.0,
    ) -> TrendScoreResult:
        now = datetime.now(UTC)
        age_hours = None
        if video.published_at:
            published = video.published_at
            if published.tzinfo is None:
                published = published.replace(tzinfo=UTC)
            age_hours = max((now - published).total_seconds() / 3600, 0)
        recency = math.exp(-age_hours / 72) if age_hours is not None else None
        freshness = math.exp(-age_hours / 168) if age_hours is not None else None
        metrics = video.metrics
        engagement_ratio = metrics.engagement_rate
        if engagement_ratio is None and metrics.views:
            engagement_ratio = (
                (metrics.likes or 0) + (metrics.comments or 0) + (metrics.shares or 0) + (metrics.saves or 0)
            ) / metrics.views
        follower_adjusted = None
        if metrics.views is not None and video.creator_follower_count:
            follower_adjusted = min(metrics.views / max(video.creator_follower_count, 1), 10) / 10
        components: dict[str, float | None] = {
            "recency": recency,
            "views": log_scale(metrics.views, 50_000_000),
            "view_velocity": log_scale(metrics.view_velocity, 1_000_000),
            "engagement_ratio": bounded(engagement_ratio, 0, 0.2),
            "engagement_velocity": log_scale(metrics.engagement_velocity, 100_000),
            "follower_adjusted": follower_adjusted,
            "cross_platform": min(max(cross_platform_count - 1, 0) / 2, 1),
            "topic_relevance": min(max(topic_relevance, 0), 1),
            "freshness": freshness,
            "originality_opportunity": min(max(originality_opportunity, 0), 1),
            "brand_safety": min(max(brand_safety, 0), 1),
        }
        available = {key: value for key, value in components.items() if value is not None}
        missing = [key for key, value in components.items() if value is None]
        denominator = sum(self.weights[key] for key in available)
        score = 100 * sum(self.weights[key] * value for key, value in available.items()) / max(denominator, 0.0001)
        metric_coverage = denominator / sum(self.weights.values())
        confidence = min(1.0, 0.25 + 0.65 * metric_coverage + 0.1 * video.data_confidence)
        explanation = sorted(
            [f"{key.replace('_', ' ').title()}: {value * 100:.0f}/100" for key, value in available.items()],
            key=lambda text: float(text.rsplit(" ", 1)[-1].split("/")[0]),
            reverse=True,
        )[:5]
        if missing:
            explanation.append(f"Confidence reduced because {', '.join(missing)} were unavailable.")
        return TrendScoreResult(
            score=round(score, 2),
            confidence=round(confidence, 3),
            components={key: round(value or 0, 4) for key, value in components.items()},
            explanation=explanation,
            missing_metrics=missing,
        )


def dedupe_key(video: NormalizedVideo) -> str:
    text = " ".join(
        part for part in [video.title or "", video.caption or "", video.topic or ""] if part
    ).lower()
    tokens = sorted({token.strip("#.,!?()[]{}") for token in text.split() if len(token) > 3})[:12]
    return "|".join(tokens) or f"{video.platform}:{video.external_video_id}"
