from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, HttpUrl


Platform = Literal["youtube", "tiktok", "instagram"]


class SourceMetricsIn(BaseModel):
    views: int | None = None
    likes: int | None = None
    comments: int | None = None
    shares: int | None = None
    saves: int | None = None
    engagement_rate: float | None = None
    view_velocity: float | None = None
    engagement_velocity: float | None = None
    status_codes: dict[str, str] = Field(default_factory=dict)


class NormalizedVideo(BaseModel):
    platform: Platform
    external_video_id: str
    canonical_url: str
    creator_external_id: str | None = None
    creator_name: str | None = None
    creator_follower_count: int | None = None
    title: str | None = None
    caption: str | None = None
    hashtags: list[str] = Field(default_factory=list)
    topic: str | None = None
    category: str | None = None
    language: str | None = None
    country: str | None = None
    published_at: datetime | None = None
    duration_seconds: float | None = None
    audio_info: dict[str, Any] | None = None
    transcript: str | None = None
    thumbnail_url: str | None = None
    data_source: str
    data_confidence: float = Field(default=0.5, ge=0, le=1)
    metrics: SourceMetricsIn = Field(default_factory=SourceMetricsIn)
    raw_response: dict[str, Any] = Field(default_factory=dict)


class TrendScoreResult(BaseModel):
    score: float = Field(ge=0, le=100)
    confidence: float = Field(ge=0, le=1)
    components: dict[str, float]
    explanation: list[str]
    missing_metrics: list[str]


class ImportVideoRequest(BaseModel):
    platform: Platform
    url: str
    title: str | None = None
    caption: str | None = None
    topic: str | None = None
    creator_name: str | None = None
    published_at: datetime | None = None
    metrics: SourceMetricsIn = Field(default_factory=SourceMetricsIn)


class BrandProfileRequest(BaseModel):
    name: str
    niche: str
    target_audience: str
    brand_voice: str
    countries: list[str] = Field(default_factory=lambda: ["US"])
    languages: list[str] = Field(default_factory=lambda: ["en"])
    topics_include: list[str] = Field(default_factory=list)
    topics_exclude: list[str] = Field(default_factory=list)
    preferred_duration_seconds: int = Field(default=30, ge=10, le=1200)
    preferred_voice: str = "neutral"
    approved: bool = False


class LoginRequest(BaseModel):
    email: str
    password: str


class ApprovalRequest(BaseModel):
    reason: str | None = None


class ScheduleRequest(BaseModel):
    cron_expression: str
    timezone: str = "America/Chicago"
    enabled: bool = True


class ExperimentRequest(BaseModel):
    name: str
    hypothesis: str
    control: dict[str, Any]
    variant: dict[str, Any]
    target_metric: str
    guardrail_metrics: list[str] = Field(default_factory=list)
    minimum_sample_size: int = Field(default=30, ge=10)
    confidence_requirement: float = Field(default=0.95, ge=0.8, le=0.999)


class ProviderConfigRequest(BaseModel):
    provider_type: str
    provider_name: str
    enabled: bool = False
    configuration: dict[str, Any] = Field(default_factory=dict)
    secret: str | None = None


class PublishRequest(BaseModel):
    platform: Platform
    platform_account_id: str | None = None
    schedule_at: datetime | None = None
    simulate: bool = True


class CreatorDiscoveryRequest(BaseModel):
    platform: Literal["youtube", "instagram", "both"] = "both"
    query: str | None = Field(default=None, max_length=200)
    hashtags: list[str] = Field(default_factory=list, max_length=10)
    instagram_usernames: list[str] = Field(default_factory=list, max_length=200)
    top_n: int = Field(default=100, ge=1, le=100)
    recent_posts_per_creator: int = Field(default=10, ge=1, le=10)
    import_latest_as_trends: bool = True


class AuthorizedMediaCaptureRequest(BaseModel):
    source_url: HttpUrl
    rights_status: Literal[
        "user_owned",
        "licensed",
        "public_domain",
        "explicit_permission",
    ]
    rights_owner: str = Field(
        min_length=1,
        max_length=255,
    )
    license_reference: str | None = None
    attribution_text: str | None = Field(
        default=None,
        max_length=500,
    )
    allow_full_reuse: bool = False


class CreatorWatchRequest(BaseModel):
    platform: Platform
    creator_name: str = Field(
        min_length=1,
        max_length=255,
    )
    external_creator_id: str = Field(
        min_length=1,
        max_length=255,
    )
    profile_url: HttpUrl | None = None
    rights_status: Literal[
        "user_owned",
        "licensed",
        "public_domain",
        "explicit_permission",
    ]
    rights_owner: str = Field(
        min_length=1,
        max_length=255,
    )
    license_reference: str | None = None
    attribution_text: str | None = Field(
        default=None,
        max_length=500,
    )
    allow_full_reuse: bool = False
    authorized_media_url_template: str | None = None
    auto_capture_and_prepare: bool = False


class PermanentDeleteRequest(BaseModel):
    confirmation: Literal["DELETE"]


class APIModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)
