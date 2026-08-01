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


def parse_tiktok_id(url: str) -> str:
    parts = [part for part in urlparse(url).path.split("/") if part]
    if "video" in parts:
        index = parts.index("video")
        if index + 1 < len(parts):
            return parts[index + 1]
    return hashlib.sha256(url.encode()).hexdigest()[:24]


class TikTokAdapter(PlatformAdapter):
    platform = "tiktok"
    api_base = "https://open.tiktokapis.com"

    def __init__(self, settings: Settings | None = None, http: ResilientHTTPClient | None = None) -> None:
        self.settings = settings or get_settings()
        self.http = http or ResilientHTTPClient()

    def connect_account(self, state: str) -> str:
        if not self.settings.tiktok_client_key:
            raise PlatformAPIError("TikTok client key is not configured")
        params = {
            "client_key": self.settings.tiktok_client_key,
            "scope": "user.info.basic,video.list,video.upload,video.publish",
            "response_type": "code",
            "redirect_uri": self.settings.tiktok_redirect_uri,
            "state": state,
        }
        return "https://www.tiktok.com/v2/auth/authorize/?" + urlencode(params)

    def exchange_code(self, code: str) -> dict[str, Any]:
        response = self.http.request(
            "POST",
            f"{self.api_base}/v2/oauth/token/",
            data={
                "client_key": self.settings.tiktok_client_key,
                "client_secret": self.settings.tiktok_client_secret,
                "code": code,
                "grant_type": "authorization_code",
                "redirect_uri": self.settings.tiktok_redirect_uri,
            },
        )
        return response.json()

    def disconnect_account(self, account_id: str) -> None:
        return None

    def refresh_authorization(self, refresh_token: str) -> dict[str, Any]:
        response = self.http.request(
            "POST",
            f"{self.api_base}/v2/oauth/token/",
            data={
                "client_key": self.settings.tiktok_client_key,
                "client_secret": self.settings.tiktok_client_secret,
                "grant_type": "refresh_token",
                "refresh_token": refresh_token,
            },
        )
        return response.json()

    def verify_permissions(self, access_token: str) -> dict[str, Any]:
        response = self.http.request(
            "GET",
            f"{self.api_base}/v2/user/info/",
            params={"fields": "open_id,union_id,avatar_url,display_name"},
            headers={"Authorization": f"Bearer {access_token}"},
        )
        return {"valid": True, "account": response.json(), "required_scopes": ["video.upload", "video.publish"]}

    def discover_trends(self, limit: int = 30) -> list[NormalizedVideo]:
        if self.settings.tiktok_commercial_provider_url and self.settings.tiktok_commercial_provider_key:
            response = self.http.request(
                "GET",
                self.settings.tiktok_commercial_provider_url,
                params={"limit": min(limit, 100)},
                headers={"Authorization": f"Bearer {self.settings.tiktok_commercial_provider_key}"},
            )
            items = response.json().get("items", [])
            return [self._normalize_provider_item(item) for item in items]
        return []

    def import_video_reference(self, url: str) -> NormalizedVideo:
        return NormalizedVideo(
            platform="tiktok",
            external_video_id=parse_tiktok_id(url),
            canonical_url=url,
            data_source="manual_url_import",
            data_confidence=0.3,
            metrics=SourceMetricsIn(
                status_codes={
                    "views": "not_retrieved_without_approved_access",
                    "shares": "not_retrieved_without_approved_access",
                    "saves": "not_exposed",
                }
            ),
        )

    def retrieve_video_metadata(self, video_id: str, access_token: str | None = None) -> NormalizedVideo:
        if not access_token:
            raise PlatformAPIError("A user-authorized TikTok token is required for video query")
        response = self.http.request(
            "POST",
            f"{self.api_base}/v2/video/query/",
            params={
                "fields": "id,create_time,cover_image_url,share_url,video_description,duration,height,width,title,embed_link,like_count,comment_count,share_count,view_count"
            },
            headers={"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"},
            json={"filters": {"video_ids": [video_id]}},
        )
        videos = response.json().get("data", {}).get("videos", [])
        if not videos:
            raise PlatformAPIError("TikTok video is unavailable to the authorized account")
        item = videos[0]
        create_time = item.get("create_time")
        published = datetime.fromtimestamp(create_time, tz=UTC) if create_time else None
        views = item.get("view_count")
        likes = item.get("like_count")
        comments = item.get("comment_count")
        shares = item.get("share_count")
        engagement = ((likes or 0) + (comments or 0) + (shares or 0)) / views if views else None
        return NormalizedVideo(
            platform="tiktok",
            external_video_id=str(item.get("id", video_id)),
            canonical_url=item.get("share_url") or f"https://www.tiktok.com/video/{video_id}",
            title=item.get("title"),
            caption=item.get("video_description"),
            published_at=published,
            duration_seconds=item.get("duration"),
            thumbnail_url=item.get("cover_image_url"),
            data_source="tiktok_display_api_authorized_video_query",
            data_confidence=0.85,
            metrics=SourceMetricsIn(
                views=views,
                likes=likes,
                comments=comments,
                shares=shares,
                engagement_rate=engagement,
                status_codes={"saves": "unsupported"},
            ),
            raw_response=item,
        )

    def retrieve_account_metrics(self, access_token: str) -> dict[str, Any]:
        response = self.http.request(
            "GET",
            f"{self.api_base}/v2/user/info/",
            params={"fields": "open_id,union_id,display_name,follower_count,following_count,likes_count,video_count"},
            headers={"Authorization": f"Bearer {access_token}"},
        )
        return response.json()

    def retrieve_post_metrics(self, post_id: str, access_token: str) -> dict[str, Any]:
        return self.retrieve_video_metadata(post_id, access_token).model_dump(mode="json")

    def validate_media(self, path: Path) -> dict[str, Any]:
        result = probe_media(path)
        result["platform_valid"] = (
            result["valid"]
            and result["video_codec"] in {"h264", "hevc"}
            and result["audio_codec"] in {"aac", None}
            and result["size_bytes"] <= 4 * 1024 * 1024 * 1024
        )
        return result

    def create_draft(self, path: Path, metadata: dict[str, Any], access_token: str) -> dict[str, Any]:
        return self._initialize_upload(path, metadata, access_token, direct=False)

    def upload_media(self, path: Path, metadata: dict[str, Any], access_token: str) -> dict[str, Any]:
        return self._initialize_upload(path, metadata, access_token, direct=True)

    def _initialize_upload(
        self, path: Path, metadata: dict[str, Any], access_token: str, *, direct: bool
    ) -> dict[str, Any]:
        validation = self.validate_media(path)
        if not validation["platform_valid"]:
            raise PlatformAPIError("Media does not meet TikTok validation requirements", payload=validation)
        endpoint = "/v2/post/publish/video/init/" if direct else "/v2/post/publish/inbox/video/init/"
        payload: dict[str, Any] = {
            "source_info": {
                "source": "FILE_UPLOAD",
                "video_size": path.stat().st_size,
                "chunk_size": path.stat().st_size,
                "total_chunk_count": 1,
            }
        }
        if direct:
            payload["post_info"] = {
                "title": metadata.get("caption", "")[:2200],
                "privacy_level": metadata.get("privacy_level", "SELF_ONLY"),
                "disable_duet": bool(metadata.get("disable_duet", False)),
                "disable_comment": bool(metadata.get("disable_comment", False)),
                "disable_stitch": bool(metadata.get("disable_stitch", False)),
                "video_cover_timestamp_ms": int(metadata.get("video_cover_timestamp_ms", 1000)),
            }
        init = self.http.request(
            "POST",
            f"{self.api_base}{endpoint}",
            headers={"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"},
            json=payload,
        ).json()
        data = init.get("data", {})
        upload_url = data.get("upload_url")
        publish_id = data.get("publish_id")
        if not upload_url or not publish_id:
            raise PlatformAPIError("TikTok did not return upload_url and publish_id", payload=init)
        size = path.stat().st_size
        with path.open("rb") as media:
            self.http.request(
                "PUT",
                upload_url,
                headers={
                    "Content-Type": "video/mp4",
                    "Content-Length": str(size),
                    "Content-Range": f"bytes 0-{size - 1}/{size}",
                },
                content=media.read(),
            )
        return {"upload_id": publish_id, "publish_id": publish_id, "mode": "direct" if direct else "draft"}

    def publish_media(self, upload_id: str, metadata: dict[str, Any], access_token: str) -> dict[str, Any]:
        return {"publish_id": upload_id, "status": "processing", "note": "Direct Post begins during upload initialization."}

    def retrieve_publish_status(self, publish_id: str, access_token: str) -> dict[str, Any]:
        response = self.http.request(
            "POST",
            f"{self.api_base}/v2/post/publish/status/fetch/",
            headers={"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"},
            json={"publish_id": publish_id},
        )
        return response.json()

    def delete_pending_upload(self, upload_id: str, access_token: str) -> dict[str, Any]:
        return {"deleted": False, "reason": "TikTok does not expose a general pending-upload deletion endpoint."}

    def handle_webhook(self, payload: dict[str, Any], signature: str | None) -> dict[str, Any]:
        return {"accepted": True, "type": payload.get("event"), "signature_present": bool(signature)}

    def health_check(self) -> AdapterHealth:
        configured = bool(self.settings.tiktok_client_key and self.settings.tiktok_client_secret)
        return AdapterHealth(
            platform=self.platform,
            status="configured" if configured else "needs_configuration",
            configured=configured,
            publishing_eligible=configured,
            analytics_eligible=configured,
            limitations=[
                "No unauthorized scraping or platform-wide discovery is performed.",
                "Research API access is limited to approved non-commercial research use.",
                "Unaudited Direct Post clients are restricted to private visibility.",
                "Direct posting requires video.publish approval and explicit creator consent.",
            ],
            details={"research_access_configured": self.settings.tiktok_research_access},
        )

    def _normalize_provider_item(self, item: dict[str, Any]) -> NormalizedVideo:
        return NormalizedVideo(
            platform="tiktok",
            external_video_id=str(item["id"]),
            canonical_url=item["url"],
            creator_external_id=item.get("creator_id"),
            creator_name=item.get("creator_name"),
            creator_follower_count=item.get("followers"),
            title=item.get("title"),
            caption=item.get("caption"),
            hashtags=item.get("hashtags", []),
            topic=item.get("topic"),
            language=item.get("language"),
            country=item.get("country"),
            duration_seconds=item.get("duration"),
            thumbnail_url=item.get("thumbnail"),
            data_source="approved_commercial_trend_provider",
            data_confidence=float(item.get("confidence", 0.7)),
            metrics=SourceMetricsIn(
                views=item.get("views"),
                likes=item.get("likes"),
                comments=item.get("comments"),
                shares=item.get("shares"),
                saves=item.get("saves"),
                view_velocity=item.get("view_velocity"),
                engagement_velocity=item.get("engagement_velocity"),
            ),
            raw_response=item,
        )
