from __future__ import annotations

from typing import Any


def per_thousand(numerator: int | float | None, denominator: int | float | None) -> float | None:
    if numerator is None or denominator in {None, 0}:
        return None
    return round(float(numerator) * 1000 / float(denominator), 4)


def normalized_post_metrics(metrics: dict[str, Any], followers: int | None = None) -> dict[str, float | None]:
    views = metrics.get("views")
    impressions = metrics.get("impressions")
    average_duration = metrics.get("average_view_duration")
    duration = metrics.get("duration")
    completion_rate = metrics.get("completion_rate")
    if completion_rate is None and average_duration is not None and duration:
        completion_rate = min(float(average_duration) / float(duration), 1.0)
    return {
        "views_per_1000_followers": per_thousand(views, followers),
        "likes_per_1000_views": per_thousand(metrics.get("likes"), views),
        "comments_per_1000_views": per_thousand(metrics.get("comments"), views),
        "shares_per_1000_views": per_thousand(metrics.get("shares"), views),
        "saves_per_1000_views": per_thousand(metrics.get("saves"), views),
        "follows_per_1000_views": per_thousand(metrics.get("follows"), views),
        "completion_rate_index": round(float(completion_rate), 4) if completion_rate is not None else None,
        "retention_index": round(float(metrics.get("retention", 0)), 4) if metrics.get("retention") is not None else None,
        "engagement_velocity": metrics.get("engagement_velocity"),
        "follower_growth_velocity": metrics.get("follower_growth_velocity"),
        "click_through_per_1000_impressions": per_thousand(metrics.get("clicks"), impressions),
    }


def multi_objective_performance(metrics: dict[str, Any]) -> float:
    positive = (
        0.16 * min(float(metrics.get("completion_rate", 0)), 1)
        + 0.16 * min(float(metrics.get("retention", 0)), 1)
        + 0.14 * min(float(metrics.get("shares_per_1000_views", 0)) / 30, 1)
        + 0.12 * min(float(metrics.get("saves_per_1000_views", 0)) / 40, 1)
        + 0.10 * min(float(metrics.get("comments_per_1000_views", 0)) / 20, 1)
        + 0.14 * min(float(metrics.get("follows_per_1000_views", 0)) / 20, 1)
        + 0.08 * min(float(metrics.get("qualified_views_index", 0)), 1)
        + 0.10 * min(float(metrics.get("topic_relevance", 0)), 1)
    )
    penalties = (
        0.25 * min(float(metrics.get("negative_feedback_rate", 0)) * 20, 1)
        + 0.30 * min(float(metrics.get("policy_warnings", 0)), 1)
        + 0.30 * min(float(metrics.get("copyright_claims", 0)), 1)
        + 0.15 * min(float(metrics.get("unfollow_rate", 0)) * 20, 1)
    )
    return round(max(0.0, min((positive - penalties) * 100, 100)), 2)
