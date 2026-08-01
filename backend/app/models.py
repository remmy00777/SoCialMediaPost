from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Index, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base


def utcnow() -> datetime:
    return datetime.now(UTC)


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
    )
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class UUIDMixin:
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))


class User(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "users"
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_admin: Mapped[bool] = mapped_column(Boolean, default=True)


class BrandProfile(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "brand_profiles"
    user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    name: Mapped[str] = mapped_column(String(200), default="My Brand")
    niche: Mapped[str] = mapped_column(String(200), default="General education")
    target_audience: Mapped[str] = mapped_column(Text, default="Curious adults")
    brand_voice: Mapped[str] = mapped_column(Text, default="Clear, credible, energetic")
    countries: Mapped[list[str]] = mapped_column(JSON, default=lambda: ["US"])
    languages: Mapped[list[str]] = mapped_column(JSON, default=lambda: ["en"])
    topics_include: Mapped[list[str]] = mapped_column(JSON, default=list)
    topics_exclude: Mapped[list[str]] = mapped_column(JSON, default=list)
    preferred_duration_seconds: Mapped[int] = mapped_column(Integer, default=30)
    preferred_voice: Mapped[str] = mapped_column(String(120), default="neutral")
    approved: Mapped[bool] = mapped_column(Boolean, default=False)


class PlatformAccount(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "platform_accounts"
    __table_args__ = (UniqueConstraint("platform", "external_account_id", name="uq_platform_account"),)
    user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    platform: Mapped[str] = mapped_column(String(32), index=True)
    account_type: Mapped[str | None] = mapped_column(String(64))
    external_account_id: Mapped[str | None] = mapped_column(String(255))
    display_name: Mapped[str | None] = mapped_column(String(255))
    authorization_status: Mapped[str] = mapped_column(String(40), default="disconnected")
    token_health: Mapped[str] = mapped_column(String(40), default="unknown")
    granted_permissions: Mapped[list[str]] = mapped_column(JSON, default=list)
    missing_permissions: Mapped[list[str]] = mapped_column(JSON, default=list)
    publishing_eligible: Mapped[bool] = mapped_column(Boolean, default=False)
    analytics_eligible: Mapped[bool] = mapped_column(Boolean, default=False)
    app_review_required: Mapped[bool] = mapped_column(Boolean, default=True)
    last_refresh_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_api_call_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    quota_status: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    raw_profile: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    error_message: Mapped[str | None] = mapped_column(Text)


class OAuthCredential(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "oauth_credentials"
    platform_account_id: Mapped[str] = mapped_column(
        ForeignKey("platform_accounts.id", ondelete="CASCADE"), unique=True, index=True
    )
    encrypted_access_token: Mapped[str | None] = mapped_column(Text)
    encrypted_refresh_token: Mapped[str | None] = mapped_column(Text)
    token_type: Mapped[str | None] = mapped_column(String(40))
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    scopes: Mapped[list[str]] = mapped_column(JSON, default=list)
    key_version: Mapped[int] = mapped_column(Integer, default=1)


class Permission(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "permissions"
    platform_account_id: Mapped[str] = mapped_column(ForeignKey("platform_accounts.id"), index=True)
    scope: Mapped[str] = mapped_column(String(255))
    granted: Mapped[bool] = mapped_column(Boolean, default=False)
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class TrendSource(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "trend_sources"
    platform: Mapped[str] = mapped_column(String(32), index=True)
    source_type: Mapped[str] = mapped_column(String(80))
    label: Mapped[str] = mapped_column(String(255))
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    limitations: Mapped[str] = mapped_column(Text, default="")
    configuration: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)


class Creator(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "creators"
    __table_args__ = (UniqueConstraint("platform", "external_creator_id", name="uq_creator_platform_id"),)
    platform: Mapped[str] = mapped_column(String(32), index=True)
    external_creator_id: Mapped[str] = mapped_column(String(255))
    name: Mapped[str | None] = mapped_column(String(255))
    follower_count: Mapped[int | None] = mapped_column(Integer)
    raw_data: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)


class SourceVideo(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "source_videos"
    __table_args__ = (UniqueConstraint("platform", "external_video_id", name="uq_source_video"),)
    platform: Mapped[str] = mapped_column(String(32), index=True)
    external_video_id: Mapped[str] = mapped_column(String(255))
    canonical_url: Mapped[str] = mapped_column(Text)
    creator_id: Mapped[str | None] = mapped_column(ForeignKey("creators.id"), index=True)
    creator_external_id: Mapped[str | None] = mapped_column(String(255))
    creator_name: Mapped[str | None] = mapped_column(String(255))
    creator_follower_count: Mapped[int | None] = mapped_column(Integer)
    title: Mapped[str | None] = mapped_column(Text)
    caption: Mapped[str | None] = mapped_column(Text)
    hashtags: Mapped[list[str]] = mapped_column(JSON, default=list)
    topic: Mapped[str | None] = mapped_column(String(255), index=True)
    category: Mapped[str | None] = mapped_column(String(255))
    language: Mapped[str | None] = mapped_column(String(32))
    country: Mapped[str | None] = mapped_column(String(16))
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    duration_seconds: Mapped[float | None] = mapped_column(Float)
    audio_info: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    transcript: Mapped[str | None] = mapped_column(Text)
    thumbnail_url: Mapped[str | None] = mapped_column(Text)
    data_source: Mapped[str] = mapped_column(String(120))
    data_confidence: Mapped[float] = mapped_column(Float, default=0.5)
    raw_response: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)


class SourceMediaAsset(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "source_media_assets"
    source_video_id: Mapped[str] = mapped_column(ForeignKey("source_videos.id"), index=True)
    uploaded_by_user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    original_filename: Mapped[str] = mapped_column(String(255))
    path: Mapped[str] = mapped_column(Text, unique=True)
    mime_type: Mapped[str] = mapped_column(String(120))
    size_bytes: Mapped[int] = mapped_column(Integer)
    sha256: Mapped[str] = mapped_column(String(64), index=True)
    media_validation: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    rights_status: Mapped[str] = mapped_column(String(40), index=True)
    rights_owner: Mapped[str] = mapped_column(String(255))
    license_reference: Mapped[str | None] = mapped_column(Text)
    allow_full_reuse: Mapped[bool] = mapped_column(Boolean, default=False)
    rights_verified_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class SourceMetric(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "source_metrics"
    source_video_id: Mapped[str] = mapped_column(ForeignKey("source_videos.id"), index=True)
    retrieved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
    views: Mapped[int | None] = mapped_column(Integer)
    likes: Mapped[int | None] = mapped_column(Integer)
    comments: Mapped[int | None] = mapped_column(Integer)
    shares: Mapped[int | None] = mapped_column(Integer)
    saves: Mapped[int | None] = mapped_column(Integer)
    engagement_rate: Mapped[float | None] = mapped_column(Float)
    view_velocity: Mapped[float | None] = mapped_column(Float)
    engagement_velocity: Mapped[float | None] = mapped_column(Float)
    status_codes: Mapped[dict[str, str]] = mapped_column(JSON, default=dict)


class TrendCandidate(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "trend_candidates"
    source_video_id: Mapped[str] = mapped_column(ForeignKey("source_videos.id"), index=True)
    trend_source_id: Mapped[str | None] = mapped_column(ForeignKey("trend_sources.id"))
    workflow_run_id: Mapped[str | None] = mapped_column(ForeignKey("workflow_runs.id"), index=True)
    rank: Mapped[int | None] = mapped_column(Integer)
    selected: Mapped[bool] = mapped_column(Boolean, default=False)
    dedupe_group: Mapped[str | None] = mapped_column(String(255))


class TrendSnapshot(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "trend_snapshots"
    trend_candidate_id: Mapped[str] = mapped_column(ForeignKey("trend_candidates.id"), index=True)
    snapshot_data: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    captured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class TrendScore(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "trend_scores"
    trend_candidate_id: Mapped[str] = mapped_column(ForeignKey("trend_candidates.id"), unique=True)
    score: Mapped[float] = mapped_column(Float, index=True)
    confidence: Mapped[float] = mapped_column(Float)
    components: Mapped[dict[str, float]] = mapped_column(JSON, default=dict)
    explanation: Mapped[list[str]] = mapped_column(JSON, default=list)
    missing_metrics: Mapped[list[str]] = mapped_column(JSON, default=list)
    model_version: Mapped[str] = mapped_column(String(80), default="transparent-v1")


class TrendAnalysis(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "trend_analyses"
    trend_candidate_id: Mapped[str] = mapped_column(ForeignKey("trend_candidates.id"), unique=True)
    observations: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    interpretations: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    confidence: Mapped[float] = mapped_column(Float, default=0.5)
    supporting_signals: Mapped[list[str]] = mapped_column(JSON, default=list)
    missing_information: Mapped[list[str]] = mapped_column(JSON, default=list)
    assumptions: Mapped[list[str]] = mapped_column(JSON, default=list)


class ContentConcept(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "content_concepts"
    trend_candidate_id: Mapped[str] = mapped_column(ForeignKey("trend_candidates.id"), index=True)
    status: Mapped[str] = mapped_column(String(40), default="candidate")
    selected: Mapped[bool] = mapped_column(Boolean, default=False)
    concept: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    component_scores: Mapped[dict[str, float]] = mapped_column(JSON, default=dict)
    total_score: Mapped[float] = mapped_column(Float, default=0)
    prompt_version: Mapped[str] = mapped_column(String(80), default="local-concept-v1")


class ContentPackage(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "content_packages"
    concept_id: Mapped[str] = mapped_column(ForeignKey("content_concepts.id"), index=True)
    status: Mapped[str] = mapped_column(String(40), default="draft", index=True)
    title: Mapped[str] = mapped_column(Text)
    storage_path: Mapped[str] = mapped_column(Text, unique=True)
    quality_score: Mapped[float] = mapped_column(Float, default=0)
    predicted_performance: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    generation_metadata: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    approval_mode: Mapped[str] = mapped_column(String(40), default="manual_export")
    idempotency_key: Mapped[str] = mapped_column(String(120), unique=True, index=True)


class PlatformVariant(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "platform_variants"
    __table_args__ = (UniqueConstraint("content_package_id", "platform", name="uq_package_platform"),)
    content_package_id: Mapped[str] = mapped_column(ForeignKey("content_packages.id"), index=True)
    platform: Mapped[str] = mapped_column(String(32), index=True)
    status: Mapped[str] = mapped_column(String(40), default="draft")
    media_path: Mapped[str | None] = mapped_column(Text)
    thumbnail_path: Mapped[str | None] = mapped_column(Text)
    subtitle_path: Mapped[str | None] = mapped_column(Text)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    media_validation: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)


class GeneratedAsset(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "generated_assets"
    content_package_id: Mapped[str] = mapped_column(ForeignKey("content_packages.id"), index=True)
    platform_variant_id: Mapped[str | None] = mapped_column(ForeignKey("platform_variants.id"))
    asset_type: Mapped[str] = mapped_column(String(80), index=True)
    path: Mapped[str] = mapped_column(Text)
    sha256: Mapped[str] = mapped_column(String(64), index=True)
    size_bytes: Mapped[int] = mapped_column(Integer)
    mime_type: Mapped[str | None] = mapped_column(String(120))
    rights_status: Mapped[str] = mapped_column(String(40), default="original")


class ApprovalRecord(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "approval_records"
    content_package_id: Mapped[str] = mapped_column(ForeignKey("content_packages.id"), index=True)
    user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"))
    action: Mapped[str] = mapped_column(String(40))
    reason: Mapped[str | None] = mapped_column(Text)


class PublicationJob(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "publication_jobs"
    platform_variant_id: Mapped[str] = mapped_column(ForeignKey("platform_variants.id"), index=True)
    platform_account_id: Mapped[str | None] = mapped_column(ForeignKey("platform_accounts.id"))
    scheduled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    status: Mapped[str] = mapped_column(String(40), default="queued", index=True)
    attempt_count: Mapped[int] = mapped_column(Integer, default=0)
    idempotency_key: Mapped[str] = mapped_column(String(160), unique=True, index=True)
    external_upload_id: Mapped[str | None] = mapped_column(String(255))
    error_message: Mapped[str | None] = mapped_column(Text)


class PlatformPost(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "platform_posts"
    publication_job_id: Mapped[str] = mapped_column(ForeignKey("publication_jobs.id"), unique=True)
    platform: Mapped[str] = mapped_column(String(32), index=True)
    external_post_id: Mapped[str] = mapped_column(String(255), index=True)
    canonical_url: Mapped[str | None] = mapped_column(Text)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(40), default="processing")
    raw_response: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)


class PostMetricSnapshot(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "post_metric_snapshots"
    platform_post_id: Mapped[str] = mapped_column(ForeignKey("platform_posts.id"), index=True)
    captured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
    metrics: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    normalized_metrics: Mapped[dict[str, float | None]] = mapped_column(JSON, default=dict)
    unsupported: Mapped[dict[str, str]] = mapped_column(JSON, default=dict)


class AccountMetricSnapshot(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "account_metric_snapshots"
    platform_account_id: Mapped[str] = mapped_column(ForeignKey("platform_accounts.id"), index=True)
    captured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
    metrics: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    normalized_metrics: Mapped[dict[str, float | None]] = mapped_column(JSON, default=dict)


class Schedule(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "schedules"
    name: Mapped[str] = mapped_column(String(120), unique=True)
    workflow_type: Mapped[str] = mapped_column(String(80), index=True)
    cron_expression: Mapped[str] = mapped_column(String(80))
    timezone: Mapped[str] = mapped_column(String(80), default="America/Chicago")
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    catch_up_policy: Mapped[str] = mapped_column(String(40), default="one_safe_run")
    last_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    next_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class WorkflowRun(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "workflow_runs"
    workflow_type: Mapped[str] = mapped_column(String(80), index=True)
    status: Mapped[str] = mapped_column(String(40), default="running", index=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    correlation_id: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    summary: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    error_message: Mapped[str | None] = mapped_column(Text)


class TaskRun(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "task_runs"
    workflow_run_id: Mapped[str] = mapped_column(ForeignKey("workflow_runs.id"), index=True)
    task_name: Mapped[str] = mapped_column(String(120), index=True)
    item_key: Mapped[str | None] = mapped_column(String(255), index=True)
    status: Mapped[str] = mapped_column(String(40), default="running")
    attempt_count: Mapped[int] = mapped_column(Integer, default=1)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    result: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    error_message: Mapped[str | None] = mapped_column(Text)


class ProviderConfiguration(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "provider_configurations"
    provider_type: Mapped[str] = mapped_column(String(80), index=True)
    provider_name: Mapped[str] = mapped_column(String(120))
    enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    configuration: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    encrypted_secret: Mapped[str | None] = mapped_column(Text)
    health_status: Mapped[str] = mapped_column(String(40), default="unknown")
    last_health_check_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class PromptVersion(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "prompt_versions"
    name: Mapped[str] = mapped_column(String(120), index=True)
    version: Mapped[int] = mapped_column(Integer)
    template: Mapped[str] = mapped_column(Text)
    schema_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    checksum: Mapped[str] = mapped_column(String(64))
    __table_args__ = (UniqueConstraint("name", "version", name="uq_prompt_version"),)


class Experiment(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "experiments"
    name: Mapped[str] = mapped_column(String(200), unique=True)
    hypothesis: Mapped[str] = mapped_column(Text)
    control: Mapped[dict[str, Any]] = mapped_column(JSON)
    variant: Mapped[dict[str, Any]] = mapped_column(JSON)
    target_metric: Mapped[str] = mapped_column(String(120))
    guardrail_metrics: Mapped[list[str]] = mapped_column(JSON, default=list)
    start_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    end_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    minimum_sample_size: Mapped[int] = mapped_column(Integer, default=30)
    confidence_requirement: Mapped[float] = mapped_column(Float, default=0.95)
    status: Mapped[str] = mapped_column(String(40), default="draft")
    decision: Mapped[str | None] = mapped_column(Text)
    rollback_version: Mapped[str | None] = mapped_column(String(120))


class ExperimentAssignment(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "experiment_assignments"
    experiment_id: Mapped[str] = mapped_column(ForeignKey("experiments.id"), index=True)
    content_package_id: Mapped[str] = mapped_column(ForeignKey("content_packages.id"), index=True)
    arm: Mapped[str] = mapped_column(String(40))
    assigned_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    __table_args__ = (UniqueConstraint("experiment_id", "content_package_id", name="uq_experiment_assignment"),)


class ExperimentResult(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "experiment_results"
    experiment_id: Mapped[str] = mapped_column(ForeignKey("experiments.id"), index=True)
    sample_size: Mapped[int] = mapped_column(Integer, default=0)
    results: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    confidence_interval: Mapped[dict[str, float]] = mapped_column(JSON, default=dict)
    decision: Mapped[str | None] = mapped_column(String(80))


class PolicyCheck(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "policy_checks"
    content_package_id: Mapped[str] = mapped_column(ForeignKey("content_packages.id"), index=True)
    platform: Mapped[str | None] = mapped_column(String(32))
    passed: Mapped[bool] = mapped_column(Boolean, default=False)
    checks: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    blocking_reasons: Mapped[list[str]] = mapped_column(JSON, default=list)
    ruleset_version: Mapped[str] = mapped_column(String(80), default="local-policy-v1")


class OriginalityCheck(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "originality_checks"
    content_package_id: Mapped[str] = mapped_column(ForeignKey("content_packages.id"), index=True)
    passed: Mapped[bool] = mapped_column(Boolean, default=False)
    component_scores: Mapped[dict[str, float]] = mapped_column(JSON, default=dict)
    thresholds: Mapped[dict[str, float]] = mapped_column(JSON, default=dict)
    blocking_reasons: Mapped[list[str]] = mapped_column(JSON, default=list)


class AuditEvent(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "audit_events"
    actor_type: Mapped[str] = mapped_column(String(40), default="system")
    actor_id: Mapped[str | None] = mapped_column(String(255))
    action: Mapped[str] = mapped_column(String(160), index=True)
    resource_type: Mapped[str | None] = mapped_column(String(120))
    resource_id: Mapped[str | None] = mapped_column(String(255), index=True)
    correlation_id: Mapped[str | None] = mapped_column(String(80), index=True)
    event_data: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    ip_address: Mapped[str | None] = mapped_column(String(64))


class Notification(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "notifications"
    notification_type: Mapped[str] = mapped_column(String(80), index=True)
    severity: Mapped[str] = mapped_column(String(24), default="info")
    title: Mapped[str] = mapped_column(String(255))
    message: Mapped[str] = mapped_column(Text)
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    delivered_channels: Mapped[list[str]] = mapped_column(JSON, default=list)


class SystemSetting(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "system_settings"
    key: Mapped[str] = mapped_column(String(160), unique=True, index=True)
    value: Mapped[Any] = mapped_column(JSON)
    sensitive: Mapped[bool] = mapped_column(Boolean, default=False)
    version: Mapped[int] = mapped_column(Integer, default=1)


class ErrorEvent(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "error_events"
    severity: Mapped[str] = mapped_column(String(24), default="error")
    component: Mapped[str] = mapped_column(String(120), index=True)
    message: Mapped[str] = mapped_column(Text)
    exception_type: Mapped[str | None] = mapped_column(String(255))
    correlation_id: Mapped[str | None] = mapped_column(String(80), index=True)
    context: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


Index("ix_source_metrics_video_retrieved", SourceMetric.source_video_id, SourceMetric.retrieved_at)
Index("ix_post_metrics_post_captured", PostMetricSnapshot.platform_post_id, PostMetricSnapshot.captured_at)
Index("ix_account_metrics_account_captured", AccountMetricSnapshot.platform_account_id, AccountMetricSnapshot.captured_at)
