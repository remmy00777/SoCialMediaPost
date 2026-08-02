from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlencode, urlparse

from app.core.config import Settings, get_settings
from app.platforms.base import AdapterHealth, PlatformAdapter
from app.platforms.http import PlatformAPIError, ResilientHTTPClient
from app.schemas import NormalizedVideo, SourceMetricsIn
from app.services.media_validation import probe_media


def parse_instagram_id(url: str) -> str:
    parts = [part for part in urlparse(url).path.split("/") if part]
    for marker in ("reel", "reels", "p", "tv"):
        if marker in parts:
            idx = parts.index(marker)
            if idx + 1 < len(parts):
                return parts[idx + 1]
    return hashlib.sha256(url.encode()).hexdigest()[:24]


class InstagramAdapter(PlatformAdapter):
    platform = "instagram"

    def __init__(self, settings: Settings | None = None, http: ResilientHTTPClient | None = None) -> None:
        self.settings = settings or get_settings()
        self.http = http or ResilientHTTPClient()

    @property
    def graph_base(self) -> str:
        return f"https://graph.facebook.com/{self.settings.meta_graph_version}"

    def connect_account(self, state: str) -> str:
        if not self.settings.meta_app_id:
            raise PlatformAPIError("Meta app ID is not configured")
        if not self.settings.meta_login_config_id:
            raise PlatformAPIError(
                "Meta Login for Business configuration ID is not configured"
            )

        params = {
            "client_id": self.settings.meta_app_id,
            "config_id": self.settings.meta_login_config_id,
            "redirect_uri": self.settings.instagram_redirect_uri,
            "state": state,
            "response_type": "code",
            "override_default_response_type": "true",
        }

        return "https://www.facebook.com/dialog/oauth?" + urlencode(params)

    def exchange_code(self, code: str) -> dict[str, Any]:
        response = self.http.request(
            "GET",
            f"{self.graph_base}/oauth/access_token",
            params={
                "client_id": self.settings.meta_app_id,
                "client_secret": self.settings.meta_app_secret,
                "redirect_uri": self.settings.instagram_redirect_uri,
                "code": code,
            },
        )

        short_lived = response.json()
        access_token = short_lived.get("access_token")

        if not access_token:
            return short_lived

        try:
            long_lived = self.http.request(
                "GET",
                f"{self.graph_base}/oauth/access_token",
                params={
                    "grant_type": "fb_exchange_token",
                    "client_id": self.settings.meta_app_id,
                    "client_secret": self.settings.meta_app_secret,
                    "fb_exchange_token": access_token,
                },
            ).json()

            return {**short_lived, **long_lived}

        except Exception:
            return short_lived

    def _page_access_token(
        self,
        user_access_token: str,
        page_id: str | None,
    ) -> str:
        if not page_id:
            return user_access_token

        response = self.http.request(
            "GET",
            f"{self.graph_base}/{page_id}",
            params={
                "fields": "access_token",
                "access_token": user_access_token,
            },
        ).json()

        return str(
            response.get("access_token")
            or user_access_token
        )

    def disconnect_account(self, account_id: str) -> None:
        return None

    def refresh_authorization(self, refresh_token: str) -> dict[str, Any]:
        response = self.http.request(
            "GET",
            f"{self.graph_base}/oauth/access_token",
            params={
                "grant_type": "fb_exchange_token",
                "client_id": self.settings.meta_app_id,
                "client_secret": self.settings.meta_app_secret,
                "fb_exchange_token": refresh_token,
            },
        )
        return response.json()

    def verify_permissions(self, access_token: str) -> dict[str, Any]:
        pages = self.http.request(
            "GET",
            f"{self.graph_base}/me/accounts",
            params={"fields": "id,name,instagram_business_account{id,username,account_type}", "access_token": access_token},
        ).json()
        eligible = [
            page for page in pages.get("data", []) if page.get("instagram_business_account")
        ]
        return {
            "valid": bool(eligible),
            "accounts": eligible,
            "required_scopes": [
                "instagram_basic",
                "instagram_content_publish",
                "instagram_manage_insights",
                "pages_show_list",
                "pages_read_engagement",
                "business_management",
            ],
        }

    def discover_trends(self, limit: int = 30) -> list[NormalizedVideo]:
        return []

    def import_video_reference(self, url: str) -> NormalizedVideo:
        return NormalizedVideo(
            platform="instagram",
            external_video_id=parse_instagram_id(url),
            canonical_url=url,
            data_source="manual_url_import",
            data_confidence=0.3,
            metrics=SourceMetricsIn(
                status_codes={
                    "views": "not_available_for_arbitrary_public_reel",
                    "shares": "not_available_for_arbitrary_public_reel",
                    "saves": "not_available_for_arbitrary_public_reel",
                }
            ),
        )

    def retrieve_video_metadata(self, video_id: str, access_token: str | None = None) -> NormalizedVideo:
        if not access_token:
            raise PlatformAPIError("Instagram access token is required")
        response = self.http.request(
            "GET",
            f"{self.graph_base}/{video_id}",
            params={
                "fields": "id,caption,media_type,media_product_type,media_url,permalink,thumbnail_url,timestamp,username,shortcode",
                "access_token": access_token,
            },
        )
        item = response.json()
        published = item.get("timestamp")
        parsed = datetime.fromisoformat(published.replace("Z", "+00:00")) if published else None
        return NormalizedVideo(
            platform="instagram",
            external_video_id=str(item["id"]),
            canonical_url=item.get("permalink") or f"https://www.instagram.com/reel/{item.get('shortcode', video_id)}/",
            creator_name=item.get("username"),
            caption=item.get("caption"),
            published_at=parsed,
            thumbnail_url=item.get("thumbnail_url"),
            data_source="instagram_owned_media_api",
            data_confidence=0.9,
            raw_response=item,
        )

    def retrieve_account_metrics(self, access_token: str) -> dict[str, Any]:
        verification = self.verify_permissions(access_token)
        return {"accounts": verification.get("accounts", []), "note": "Use the selected Instagram professional account ID for insights."}

    def retrieve_post_metrics(self, post_id: str, access_token: str) -> dict[str, Any]:
        response = self.http.request(
            "GET",
            f"{self.graph_base}/{post_id}/insights",
            params={
                "metric": "views,reach,likes,comments,shares,saved,total_interactions",
                "access_token": access_token,
            },
        )
        return response.json()

    def validate_media(self, path: Path) -> dict[str, Any]:
        result = probe_media(path)
        result["platform_valid"] = (
            result["valid"]
            and result["video_codec"] in {"h264", "avc1"}
            and result["audio_codec"] in {"aac", None}
            and result["size_bytes"] <= 300 * 1024 * 1024
        )
        return result

    def create_draft(self, path: Path, metadata: dict[str, Any], access_token: str) -> dict[str, Any]:
        return self.upload_media(path, {**metadata, "published": False}, access_token)

    def upload_media(self, path: Path, metadata: dict[str, Any], access_token: str) -> dict[str, Any]:
        validation = self.validate_media(path)
        if not validation["platform_valid"]:
            raise PlatformAPIError("Media does not meet Instagram validation requirements", payload=validation)
        ig_user_id = metadata.get("ig_user_id")
        if not ig_user_id:
            raise PlatformAPIError("ig_user_id is required for Instagram publishing")

        page_access_token = self._page_access_token(
            access_token,
            metadata.get("page_id"),
        )

        container = self.http.request(
            "POST",
            f"{self.graph_base}/{ig_user_id}/media",
            data={
                "media_type": "REELS",
                "upload_type": "resumable",
                "caption": metadata.get("caption", "")[:2200],
                "share_to_feed": str(bool(metadata.get("share_to_feed", True))).lower(),
                "access_token": page_access_token,
            },
        ).json()
        container_id = container.get("id")
        upload_uri = container.get("uri") or container.get("upload_url")
        if not container_id:
            raise PlatformAPIError("Instagram did not return a media container ID", payload=container)
        upload_url = upload_uri or f"https://rupload.facebook.com/ig-api-upload/{self.settings.meta_graph_version}/{container_id}"
        with path.open("rb") as media:
            upload_result = self.http.request(
                "POST",
                upload_url,
                headers={
                    "Authorization": f"OAuth {page_access_token}",
                    "offset": "0",
                    "file_size": str(path.stat().st_size),
                    "Content-Type": "application/octet-stream",
                },
                content=media.read(),
            ).json()
        return {"upload_id": container_id, "container_id": container_id, "upload_result": upload_result}

    def publish_media(self, upload_id: str, metadata: dict[str, Any], access_token: str) -> dict[str, Any]:
        ig_user_id = metadata.get("ig_user_id")
        if not ig_user_id:
            raise PlatformAPIError("ig_user_id is required for Instagram publishing")

        page_access_token = self._page_access_token(
            access_token,
            metadata.get("page_id"),
        )

        response = self.http.request(
            "POST",
            f"{self.graph_base}/{ig_user_id}/media_publish",
            data={"creation_id": upload_id, "access_token": page_access_token},
        )
        return response.json()

    def retrieve_publish_status(self, publish_id: str, access_token: str) -> dict[str, Any]:
        response = self.http.request(
            "GET",
            f"{self.graph_base}/{publish_id}",
            params={"fields": "status_code,status", "access_token": access_token},
        )
        return response.json()

    def delete_pending_upload(self, upload_id: str, access_token: str) -> dict[str, Any]:
        return {"deleted": False, "reason": "Instagram does not expose a general pending-container deletion endpoint."}

    def handle_webhook(self, payload: dict[str, Any], signature: str | None) -> dict[str, Any]:
        return {"accepted": True, "entries": len(payload.get("entry", [])), "signature_present": bool(signature)}

    def health_check(self) -> AdapterHealth:
        configured = bool(
            self.settings.meta_app_id
            and self.settings.meta_app_secret
            and self.settings.meta_login_config_id
        )
        return AdapterHealth(
            platform=self.platform,
            status="configured" if configured else "needs_configuration",
            configured=configured,
            publishing_eligible=configured,
            analytics_eligible=configured,
            limitations=[
                "Official publishing and insights require an eligible Instagram professional account.",
                "Owned-account insights are not platform-wide trend discovery.",
                "Arbitrary public Reel analytics are not available through the owned-media API.",
                "App review and granted permissions may be required before non-role users can connect.",
            ],
        )
