from __future__ import annotations

import ipaddress
import os
import secrets
import socket
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlparse, urlunparse

import httpx
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.security import secure_filename
from app.models import SourceMediaAsset, SourceVideo, TrendCandidate
from app.services.audit import record_audit
from app.services.media_validation import probe_media
from app.services.storage import StorageManager

AUTHORIZED_RIGHTS = {"user_owned", "licensed", "public_domain", "explicit_permission"}
ALLOWED_MIME_TYPES = {
    "video/mp4": ".mp4",
    "video/quicktime": ".mov",
    "video/webm": ".webm",
    "video/x-m4v": ".m4v",
}
PROHIBITED_PLATFORM_HOSTS = {
    "youtube.com", "youtu.be", "googlevideo.com", "instagram.com",
    "cdninstagram.com", "fbcdn.net", "tiktok.com", "tiktokcdn.com", "tiktokv.com",
}


class AuthorizedMediaError(RuntimeError):
    pass


class AuthorizedMediaService:
    def __init__(self, db: Session, settings: Settings | None = None) -> None:
        self.db = db
        self.settings = settings or get_settings()
        self.storage = StorageManager(self.settings)

    def capture_for_candidate(
        self,
        candidate_id: str,
        *,
        source_url: str,
        rights_status: str,
        rights_owner: str,
        license_reference: str | None,
        attribution_text: str | None,
        allow_full_reuse: bool,
        user_id: str | None,
    ) -> SourceMediaAsset:
        candidate = self.db.get(TrendCandidate, candidate_id)
        if not candidate or candidate.deleted_at is not None:
            raise AuthorizedMediaError("Trend candidate was not found")
        source_video = self.db.get(SourceVideo, candidate.source_video_id)
        if not source_video:
            raise AuthorizedMediaError("Source video record was not found")

        self._validate_rights(rights_status, rights_owner, license_reference, allow_full_reuse)
        parsed = urlparse(source_url)
        host = (parsed.hostname or "").lower().rstrip(".")
        if parsed.scheme != "https" or not host:
            raise AuthorizedMediaError("Authorized media URL must use HTTPS")
        if self._matches_prohibited_host(host):
            raise AuthorizedMediaError("Platform page and CDN URLs cannot be used for full-media capture")
        if host not in self.settings.authorized_media_host_set:
            raise AuthorizedMediaError("Media host is not in AUTHORIZED_MEDIA_HOSTS")
        self._reject_private_destination(host)

        sanitized_url = urlunparse((parsed.scheme, parsed.netloc, parsed.path, "", "", ""))
        original_name = secure_filename(Path(parsed.path).name or "source.mp4")
        directory = self.storage.source_media_dir(candidate_id)
        temporary = self.storage.ensure_inside_root(
            directory / f".capture-{secrets.token_hex(8)}.uploading"
        )
        destination: Path | None = None
        size = 0
        mime_type = ""

        try:
            with httpx.Client(
                timeout=httpx.Timeout(90.0, connect=15.0),
                follow_redirects=False,
            ) as client:
                with client.stream(
                    "GET",
                    source_url,
                    headers={"User-Agent": "SoCialMediaPost/1.0"},
                ) as response:
                    if 300 <= response.status_code < 400:
                        raise AuthorizedMediaError("Redirects are not accepted for authorized media capture")
                    if response.status_code >= 400:
                        raise AuthorizedMediaError(
                            f"Authorized media host returned HTTP {response.status_code}"
                        )
                    mime_type = response.headers.get("content-type", "").split(";", 1)[0].lower()
                    suffix = ALLOWED_MIME_TYPES.get(mime_type)
                    if not suffix:
                        raise AuthorizedMediaError("Authorized source must be MP4, MOV, M4V, or WebM")
                    declared_length = response.headers.get("content-length")
                    if declared_length and int(declared_length) > self.settings.source_media_max_bytes:
                        raise AuthorizedMediaError("Authorized source exceeds the configured size limit")

                    destination = self.storage.ensure_inside_root(
                        directory / f"source-{secrets.token_hex(8)}{suffix}"
                    )
                    with temporary.open("wb") as handle:
                        for chunk in response.iter_bytes(1024 * 1024):
                            if not chunk:
                                continue
                            size += len(chunk)
                            if size > self.settings.source_media_max_bytes:
                                raise AuthorizedMediaError("Authorized source exceeds the configured size limit")
                            handle.write(chunk)
                        handle.flush()
                        os.fsync(handle.fileno())

            if not destination:
                raise AuthorizedMediaError("Authorized source destination was not created")
            os.replace(temporary, destination)
            validation = probe_media(destination)
            duration = float(validation.get("duration") or 0)
            if not validation.get("valid") or duration <= 0:
                raise AuthorizedMediaError("Captured media failed FFmpeg validation")
            if duration > self.settings.source_media_max_duration_seconds:
                raise AuthorizedMediaError("Captured media exceeds SOURCE_MEDIA_MAX_DURATION_SECONDS")

            final_attribution = (
                attribution_text.strip()
                if attribution_text and attribution_text.strip()
                else f"Original creator: {source_video.creator_name or rights_owner}"
            )
            validation = {
                **validation,
                "captured_via": "authorized_https_delivery",
                "source_url": sanitized_url,
                "source_host": host,
                "attribution_text": final_attribution,
            }

            existing = self.db.execute(
                select(SourceMediaAsset)
                .where(
                    SourceMediaAsset.source_video_id == source_video.id,
                    SourceMediaAsset.deleted_at.is_(None),
                )
                .order_by(desc(SourceMediaAsset.created_at))
            ).scalars().all()
            for old in existing:
                try:
                    self.storage.ensure_inside_root(Path(old.path)).unlink(missing_ok=True)
                except ValueError:
                    pass
                old.deleted_at = datetime.now(UTC)

            asset = SourceMediaAsset(
                source_video_id=source_video.id,
                uploaded_by_user_id=user_id,
                original_filename=original_name,
                path=str(destination),
                mime_type=mime_type,
                size_bytes=size,
                sha256=self.storage.sha256(destination),
                media_validation=validation,
                rights_status=rights_status,
                rights_owner=rights_owner.strip(),
                license_reference=license_reference.strip() if license_reference else None,
                allow_full_reuse=True,
                rights_verified_at=datetime.now(UTC),
            )
            self.db.add(asset)
            self.db.flush()
            record_audit(
                self.db,
                "source_media.captured_from_authorized_delivery",
                resource_type="source_media_asset",
                resource_id=asset.id,
                actor_id=user_id,
                event_data={
                    "candidate_id": candidate_id,
                    "source_host": host,
                    "rights_status": rights_status,
                    "size_bytes": size,
                    "duration_seconds": duration,
                    "manual_post_only": True,
                },
            )
            self.db.commit()
            return asset
        except Exception:
            temporary.unlink(missing_ok=True)
            if destination:
                destination.unlink(missing_ok=True)
            raise

    @staticmethod
    def _validate_rights(
        rights_status: str,
        rights_owner: str,
        license_reference: str | None,
        allow_full_reuse: bool,
    ) -> None:
        if rights_status not in AUTHORIZED_RIGHTS:
            raise AuthorizedMediaError("Unsupported rights status")
        if not rights_owner.strip():
            raise AuthorizedMediaError("Rights owner is required")
        if not allow_full_reuse:
            raise AuthorizedMediaError("Full reuse must be explicitly authorized")
        if (
            rights_status in {"licensed", "public_domain", "explicit_permission"}
            and not (license_reference or "").strip()
        ):
            raise AuthorizedMediaError("License, permission, or public-domain reference is required")

    @staticmethod
    def _matches_prohibited_host(host: str) -> bool:
        return any(host == blocked or host.endswith(f".{blocked}") for blocked in PROHIBITED_PLATFORM_HOSTS)

    @staticmethod
    def _reject_private_destination(host: str) -> None:
        try:
            addresses = {
                item[4][0]
                for item in socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)
            }
        except socket.gaierror as exc:
            raise AuthorizedMediaError("Media host could not be resolved") from exc
        for value in addresses:
            address = ipaddress.ip_address(value)
            if (
                address.is_private or address.is_loopback or address.is_link_local
                or address.is_multicast or address.is_reserved or address.is_unspecified
            ):
                raise AuthorizedMediaError(
                    "Authorized media host resolved to a blocked network address"
                )
