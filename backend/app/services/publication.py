from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.security import SecretBox
from app.models import (
    ContentPackage,
    ErrorEvent,
    OAuthCredential,
    OriginalityCheck,
    PlatformAccount,
    PlatformPost,
    PlatformVariant,
    PolicyCheck,
    PublicationJob,
    SystemSetting,
)
from app.platforms.registry import PlatformRegistry, registry
from app.services.audit import record_audit


class PublicationBlocked(RuntimeError):
    pass


class PublicationService:
    """Fresh preflight and idempotent official-platform publication orchestration."""

    def __init__(
        self,
        db: Session,
        settings: Settings | None = None,
        adapters: PlatformRegistry | None = None,
    ) -> None:
        self.db = db
        self.settings = settings or get_settings()
        self.adapters = adapters or registry

    def process(self, job_id: str, *, require_auto_enabled: bool = False) -> PlatformPost:
        job = self.db.get(PublicationJob, job_id)
        if not job:
            raise PublicationBlocked("Publication job not found")
        existing = self.db.execute(
            select(PlatformPost).where(PlatformPost.publication_job_id == job.id)
        ).scalar_one_or_none()
        if existing:
            return existing
        try:
            job.attempt_count += 1
            job.status = "validating"
            self.db.flush()
            variant, package, account, credential = self._preflight(job, require_auto_enabled)
            adapter = self.adapters.get(variant.platform)
            access_token = self._fresh_token(adapter, account, credential)
            permission_result = adapter.verify_permissions(access_token)
            if not permission_result.get("valid"):
                raise PublicationBlocked("Fresh permission verification failed")
            media_path = Path(variant.media_path or "")
            media_result = adapter.validate_media(media_path)
            if not media_result.get("platform_valid"):
                raise PublicationBlocked("Fresh platform media validation failed")
            metadata = dict(variant.metadata_json)
            metadata = self._platform_metadata(variant.platform, account, metadata)
            upload = adapter.upload_media(media_path, metadata, access_token)
            upload_id = str(upload.get("upload_id") or upload.get("publish_id") or upload.get("id") or "")
            if not upload_id:
                raise RuntimeError("Platform upload did not return an upload identifier")
            job.external_upload_id = upload_id
            job.status = "publishing"
            self.db.flush()
            published = adapter.publish_media(upload_id, metadata, access_token)
            external_post_id = str(
                published.get("id")
                or published.get("publish_id")
                or published.get("video_id")
                or upload_id
            )
            post = PlatformPost(
                publication_job_id=job.id,
                platform=variant.platform,
                external_post_id=external_post_id,
                canonical_url=published.get("canonical_url") or published.get("permalink"),
                published_at=datetime.now(UTC),
                status=str(published.get("status") or "processing"),
                raw_response={"upload": upload, "publish": published},
            )
            self.db.add(post)
            job.status = "submitted"
            job.error_message = None
            variant.status = "published_pending"
            account.last_api_call_at = datetime.now(UTC)
            record_audit(
                self.db,
                "publication.submitted",
                resource_type="publication_job",
                resource_id=job.id,
                event_data={"platform": variant.platform, "external_post_id": external_post_id},
            )
            self.db.commit()
            return post
        except Exception as exc:
            self.db.rollback()
            job = self.db.get(PublicationJob, job_id)
            if job:
                job.status = "blocked" if isinstance(exc, PublicationBlocked) else "failed"
                job.error_message = str(exc)[:2000]
                self.db.add(
                    ErrorEvent(
                        component="publication",
                        message=str(exc)[:2000],
                        exception_type=type(exc).__name__,
                        context={"publication_job_id": job_id},
                    )
                )
                record_audit(
                    self.db,
                    "publication.failed",
                    resource_type="publication_job",
                    resource_id=job.id,
                    event_data={"error_type": type(exc).__name__},
                )
                self.db.commit()
            raise

    def poll(self, post_id: str) -> PlatformPost:
        post = self.db.get(PlatformPost, post_id)
        if not post:
            raise PublicationBlocked("Platform post not found")
        job = self.db.get(PublicationJob, post.publication_job_id)
        if not job or not job.platform_account_id:
            raise PublicationBlocked("Publication account is unavailable")
        account = self.db.get(PlatformAccount, job.platform_account_id)
        credential = self.db.execute(
            select(OAuthCredential).where(OAuthCredential.platform_account_id == account.id)
        ).scalar_one_or_none()
        if not credential:
            raise PublicationBlocked("OAuth credential is unavailable")
        adapter = self.adapters.get(post.platform)
        access_token = self._fresh_token(adapter, account, credential)
        status = adapter.retrieve_publish_status(post.external_post_id, access_token)
        post.raw_response = {**post.raw_response, "latest_status": status}
        normalized = self._status_name(status)
        post.status = normalized
        if normalized in {"published", "succeeded", "complete"}:
            job.status = "published"
            variant = self.db.get(PlatformVariant, job.platform_variant_id)
            if variant:
                variant.status = "published"
        elif normalized in {"failed", "error"}:
            job.status = "failed"
        account.last_api_call_at = datetime.now(UTC)
        self.db.commit()
        return post

    def _preflight(
        self, job: PublicationJob, require_auto_enabled: bool
    ) -> tuple[PlatformVariant, ContentPackage, PlatformAccount, OAuthCredential]:
        pause = self.db.execute(
            select(SystemSetting).where(SystemSetting.key == "global_pause")
        ).scalar_one_or_none()
        if bool(pause.value) if pause else self.settings.global_pause:
            raise PublicationBlocked("Global automation pause is active")
        if require_auto_enabled and not self.settings.auto_publish_enabled:
            raise PublicationBlocked("Automatic publishing is not enabled")
        if job.scheduled_at and self._as_utc(job.scheduled_at) > datetime.now(UTC):
            raise PublicationBlocked("Publication job is not due")
        variant = self.db.get(PlatformVariant, job.platform_variant_id)
        if not variant:
            raise PublicationBlocked("Platform variant not found")
        package = self.db.get(ContentPackage, variant.content_package_id)
        if not package or package.status not in {"ready_to_post", "approved", "scheduled"}:
            raise PublicationBlocked("Content package has not passed review")
        policy = self.db.execute(
            select(PolicyCheck).where(PolicyCheck.content_package_id == package.id)
        ).scalars().first()
        originality = self.db.execute(
            select(OriginalityCheck).where(OriginalityCheck.content_package_id == package.id)
        ).scalars().first()
        if not policy or not policy.passed:
            raise PublicationBlocked("Policy gate did not pass")
        if not originality or not originality.passed:
            raise PublicationBlocked("Originality gate did not pass")
        if package.quality_score < 70:
            raise PublicationBlocked("Content quality score is below the publishing threshold")
        if not variant.media_path or not Path(variant.media_path).is_file():
            raise PublicationBlocked("Validated media file is missing")
        account = self.db.get(PlatformAccount, job.platform_account_id) if job.platform_account_id else None
        if not account:
            account = self.db.execute(
                select(PlatformAccount).where(
                    PlatformAccount.platform == variant.platform,
                    PlatformAccount.authorization_status == "connected",
                    PlatformAccount.deleted_at.is_(None),
                )
            ).scalars().first()
            if account:
                job.platform_account_id = account.id
        if not account or not account.publishing_eligible:
            raise PublicationBlocked("Connected account is not eligible for publishing")
        if account.token_health not in {"healthy", "refresh_due", "unknown"}:
            raise PublicationBlocked("Account token health blocks publishing")
        credential = self.db.execute(
            select(OAuthCredential).where(OAuthCredential.platform_account_id == account.id)
        ).scalar_one_or_none()
        if not credential or not credential.encrypted_access_token:
            raise PublicationBlocked("Encrypted OAuth access token is unavailable")
        return variant, package, account, credential

    def _fresh_token(self, adapter: Any, account: PlatformAccount, credential: OAuthCredential) -> str:
        box = SecretBox()
        if credential.expires_at and self._as_utc(credential.expires_at) <= datetime.now(UTC) + timedelta(minutes=5):
            if not credential.encrypted_refresh_token:
                account.token_health = "expired"
                self.db.commit()
                raise PublicationBlocked("OAuth token expired and no refresh token is available")
            refresh = adapter.refresh_authorization(box.decrypt(credential.encrypted_refresh_token))
            token = refresh.get("access_token")
            if not token:
                account.token_health = "refresh_failed"
                self.db.commit()
                raise PublicationBlocked("OAuth refresh did not return an access token")
            credential.encrypted_access_token = box.encrypt(token)
            if refresh.get("refresh_token"):
                credential.encrypted_refresh_token = box.encrypt(refresh["refresh_token"])
            if refresh.get("expires_in"):
                credential.expires_at = datetime.now(UTC) + timedelta(seconds=int(refresh["expires_in"]))
            account.last_refresh_at = datetime.now(UTC)
            account.token_health = "healthy"
            self.db.flush()
            return token
        return box.decrypt(credential.encrypted_access_token)


    @staticmethod
    def _as_utc(value: datetime) -> datetime:
        return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)

    @staticmethod
    def _platform_metadata(platform: str, account: PlatformAccount, metadata: dict[str, Any]) -> dict[str, Any]:
        if platform == "instagram":
            raw_profile = account.raw_profile or {}
            instagram_profile = (
                raw_profile.get("instagram_business_account")
                or {}
            )

            metadata.setdefault(
                "ig_user_id",
                instagram_profile.get("id")
                or account.external_account_id,
            )

            metadata.setdefault(
                "page_id",
                raw_profile.get("page_id")
                or raw_profile.get("id"),
            )
        if platform == "tiktok" and account.app_review_required:
            metadata["privacy_level"] = "SELF_ONLY"
        if platform == "youtube":
            metadata.setdefault("privacyStatus", "private")
        return metadata

    @staticmethod
    def _status_name(payload: dict[str, Any]) -> str:
        candidates = [
            payload.get("status"),
            payload.get("status_code"),
            (payload.get("data") or {}).get("status"),
            (payload.get("data") or {}).get("status_code"),
        ]
        return str(next((value for value in candidates if value), "processing")).lower()
