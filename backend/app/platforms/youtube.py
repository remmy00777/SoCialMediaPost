from __future__ import annotations

import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlencode, urlparse, parse_qs

from app.core.config import Settings, get_settings
from app.platforms.base import AdapterHealth, PlatformAdapter
from app.platforms.http import PlatformAPIError, ResilientHTTPClient
from app.schemas import NormalizedVideo, SourceMetricsIn
from app.services.media_validation import probe_media


_DURATION_RE = re.compile(
    r"P(?:(?P<days>\d+)D)?(?:T(?:(?P<hours>\d+)H)?(?:(?P<minutes>\d+)M)?(?:(?P<seconds>\d+)S)?)?"
)


def parse_iso8601_duration(value: str | None) -> float | None:
    if not value:
        return None
    match = _DURATION_RE.fullmatch(value)
    if not match:
        return None
    parts = {key: int(number or 0) for key, number in match.groupdict().items()}
    return float(parts["days"] * 86400 + parts["hours"] * 3600 + parts["minutes"] * 60 + parts["seconds"])


def parse_youtube_id(url: str) -> str:
    parsed = urlparse(url)
    if parsed.netloc in {"youtu.be", "www.youtu.be"}:
        return parsed.path.strip("/").split("/")[0]
    if parsed.netloc.endswith("youtube.com"):
        if parsed.path == "/watch":
            return parse_qs(parsed.query).get("v", [""])[0]
        for prefix in ("/shorts/", "/embed/", "/live/"):
            if parsed.path.startswith(prefix):
                return parsed.path[len(prefix):].split("/")[0]
    raise ValueError("Unsupported YouTube URL")


class YouTubeAdapter(PlatformAdapter):
    platform = "youtube"
    api_base = "https://www.googleapis.com/youtube/v3"
    upload_base = "https://www.googleapis.com/upload/youtube/v3"

    def __init__(self, settings: Settings | None = None, http: ResilientHTTPClient | None = None) -> None:
        self.settings = settings or get_settings()
        self.http = http or ResilientHTTPClient()

    def connect_account(self, state: str) -> str:
        if not self.settings.youtube_client_id:
            raise PlatformAPIError("YouTube OAuth client ID is not configured")
        params = {
            "client_id": self.settings.youtube_client_id,
            "redirect_uri": self.settings.youtube_redirect_uri,
            "response_type": "code",
            "access_type": "offline",
            "prompt": "consent",
            "state": state,
            "scope": " ".join(
                [
                    "https://www.googleapis.com/auth/youtube.upload",
                    "https://www.googleapis.com/auth/youtube.readonly",
                    "https://www.googleapis.com/auth/yt-analytics.readonly",
                ]
            ),
        }
        return "https://accounts.google.com/o/oauth2/v2/auth?" + urlencode(params)

    def exchange_code(self, code: str) -> dict[str, Any]:
        response = self.http.request(
            "POST",
            "https://oauth2.googleapis.com/token",
            data={
                "code": code,
                "client_id": self.settings.youtube_client_id,
                "client_secret": self.settings.youtube_client_secret,
                "redirect_uri": self.settings.youtube_redirect_uri,
                "grant_type": "authorization_code",
            },
        )
        return response.json()

    def disconnect_account(self, account_id: str) -> None:
        return None

    def refresh_authorization(self, refresh_token: str) -> dict[str, Any]:
        response = self.http.request(
            "POST",
            "https://oauth2.googleapis.com/token",
            data={
                "client_id": self.settings.youtube_client_id,
                "client_secret": self.settings.youtube_client_secret,
                "refresh_token": refresh_token,
                "grant_type": "refresh_token",
            },
        )
        return response.json()

    def verify_permissions(self, access_token: str) -> dict[str, Any]:
        response = self.http.request(
            "GET",
            f"{self.api_base}/channels",
            params={"part": "snippet,statistics", "mine": "true"},
            headers={"Authorization": f"Bearer {access_token}"},
        )
        data = response.json()
        items = data.get("items", [])
        return {
            "valid": bool(items),
            "account": items[0] if items else None,
            "required_scopes": ["youtube.upload", "youtube.readonly", "yt-analytics.readonly"],
        }

    def discover_trends(self, limit: int = 30) -> list[NormalizedVideo]:
        if not self.settings.youtube_api_key:
            return []
        response = self.http.request(
            "GET",
            f"{self.api_base}/videos",
            params={
                "part": "snippet,statistics,contentDetails",
                "chart": "mostPopular",
                "regionCode": self.settings.youtube_region,
                "videoCategoryId": self.settings.youtube_category_id,
                "maxResults": min(limit, 50),
                "key": self.settings.youtube_api_key,
            },
        )
        return [self._normalize(item, source="youtube_most_popular_chart") for item in response.json().get("items", [])]

    def import_video_reference(self, url: str) -> NormalizedVideo:
        video_id = parse_youtube_id(url)
        if self.settings.youtube_api_key:
            return self.retrieve_video_metadata(video_id)
        return NormalizedVideo(
            platform="youtube",
            external_video_id=video_id,
            canonical_url=f"https://www.youtube.com/watch?v={video_id}",
            data_source="manual_url_import",
            data_confidence=0.35,
        )

    def retrieve_video_metadata(self, video_id: str, access_token: str | None = None) -> NormalizedVideo:
        params = {"part": "snippet,statistics,contentDetails", "id": video_id}
        headers: dict[str, str] = {}
        if access_token:
            headers["Authorization"] = f"Bearer {access_token}"
        elif self.settings.youtube_api_key:
            params["key"] = self.settings.youtube_api_key
        else:
            raise PlatformAPIError("YouTube API key or access token is required")
        response = self.http.request("GET", f"{self.api_base}/videos", params=params, headers=headers)
        items = response.json().get("items", [])
        if not items:
            raise PlatformAPIError("YouTube video was not found or is not accessible")
        return self._normalize(items[0], source="youtube_videos_list")

    def retrieve_account_metrics(self, access_token: str) -> dict[str, Any]:
        response = self.http.request(
            "GET",
            f"{self.api_base}/channels",
            params={"part": "snippet,statistics", "mine": "true"},
            headers={"Authorization": f"Bearer {access_token}"},
        )
        return response.json()

    def retrieve_post_metrics(self, post_id: str, access_token: str) -> dict[str, Any]:
        response = self.http.request(
            "GET",
            f"{self.api_base}/videos",
            params={"part": "statistics,contentDetails,status", "id": post_id},
            headers={"Authorization": f"Bearer {access_token}"},
        )
        return response.json()

    def validate_media(self, path: Path) -> dict[str, Any]:
        result = probe_media(path)
        result["platform_valid"] = (
            result["valid"]
            and result["video_codec"] in {"h264", "avc1"}
            and result["audio_codec"] in {"aac", None}
        )
        return result

    def create_draft(self, path: Path, metadata: dict[str, Any], access_token: str) -> dict[str, Any]:
        data = dict(metadata)
        data.setdefault("privacyStatus", "private")
        return self.upload_media(path, data, access_token)

    def upload_media(self, path: Path, metadata: dict[str, Any], access_token: str) -> dict[str, Any]:
        validation = self.validate_media(path)
        if not validation["platform_valid"]:
            raise PlatformAPIError("Media does not meet YouTube validation requirements", payload=validation)
        body = {
            "snippet": {
                "title": metadata.get("title", "Untitled video")[:100],
                "description": metadata.get("description", "")[:5000],
                "tags": metadata.get("tags", [])[:500],
                "categoryId": str(metadata.get("categoryId", "22")),
            },
            "status": {
                "privacyStatus": metadata.get("privacyStatus", "private"),
                "selfDeclaredMadeForKids": bool(metadata.get("madeForKids", False)),
            },
        }
        init = self.http.request(
            "POST",
            f"{self.upload_base}/videos",
            params={"uploadType": "resumable", "part": "snippet,status"},
            headers={
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json; charset=UTF-8",
                "X-Upload-Content-Length": str(path.stat().st_size),
                "X-Upload-Content-Type": "video/mp4",
            },
            json=body,
        )
        upload_url = init.headers.get("location")
        if not upload_url:
            raise PlatformAPIError("YouTube did not return a resumable upload URL")
        with path.open("rb") as media:
            uploaded = self.http.request(
                "PUT",
                upload_url,
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "Content-Type": "video/mp4",
                    "Content-Length": str(path.stat().st_size),
                },
                content=media.read(),
            )
        result = uploaded.json()
        result["upload_id"] = result.get("id")
        return result

    def publish_media(self, upload_id: str, metadata: dict[str, Any], access_token: str) -> dict[str, Any]:
        privacy = metadata.get("privacyStatus", "public")
        response = self.http.request(
            "PUT",
            f"{self.api_base}/videos",
            params={"part": "status"},
            headers={"Authorization": f"Bearer {access_token}"},
            json={"id": upload_id, "status": {"privacyStatus": privacy}},
        )
        return response.json()

    def retrieve_publish_status(self, publish_id: str, access_token: str) -> dict[str, Any]:
        response = self.http.request(
            "GET",
            f"{self.api_base}/videos",
            params={"part": "status,processingDetails", "id": publish_id},
            headers={"Authorization": f"Bearer {access_token}"},
        )
        return response.json()

    def delete_pending_upload(self, upload_id: str, access_token: str) -> dict[str, Any]:
        self.http.request(
            "DELETE",
            f"{self.api_base}/videos",
            params={"id": upload_id},
            headers={"Authorization": f"Bearer {access_token}"},
        )
        return {"deleted": True, "id": upload_id}

    def handle_webhook(self, payload: dict[str, Any], signature: str | None) -> dict[str, Any]:
        return {"accepted": True, "event": payload.get("event"), "signature_present": bool(signature)}

    def health_check(self) -> AdapterHealth:
        configured = bool(self.settings.youtube_api_key or self.settings.youtube_client_id)
        return AdapterHealth(
            platform=self.platform,
            status="configured" if configured else "needs_configuration",
            configured=configured,
            publishing_eligible=bool(self.settings.youtube_client_id and self.settings.youtube_client_secret),
            analytics_eligible=bool(self.settings.youtube_client_id and self.settings.youtube_client_secret),
            limitations=[
                "The mostPopular chart is not the historical YouTube Trending page.",
                "OAuth consent and channel authorization are required for uploads and owned analytics.",
                "Shorts view counts use the post-March-2025 counting definition.",
            ],
        )

    def _normalize(self, item: dict[str, Any], source: str) -> NormalizedVideo:
        snippet = item.get("snippet", {})
        statistics = item.get("statistics", {})
        content = item.get("contentDetails", {})
        published_at = snippet.get("publishedAt")
        parsed_date = datetime.fromisoformat(published_at.replace("Z", "+00:00")) if published_at else None
        views = int(statistics["viewCount"]) if statistics.get("viewCount") is not None else None
        likes = int(statistics["likeCount"]) if statistics.get("likeCount") is not None else None
        comments = int(statistics["commentCount"]) if statistics.get("commentCount") is not None else None
        engagement = ((likes or 0) + (comments or 0)) / views if views else None
        age_hours = max((datetime.now(UTC) - parsed_date).total_seconds() / 3600, 1) if parsed_date else None
        thumbnails = snippet.get("thumbnails", {})
        thumbnail = (thumbnails.get("maxres") or thumbnails.get("high") or thumbnails.get("default") or {}).get("url")
        return NormalizedVideo(
            platform="youtube",
            external_video_id=item["id"],
            canonical_url=f"https://www.youtube.com/watch?v={item['id']}",
            creator_external_id=snippet.get("channelId"),
            creator_name=snippet.get("channelTitle"),
            title=snippet.get("title"),
            caption=snippet.get("description"),
            hashtags=[tag for tag in snippet.get("tags", []) if tag.startswith("#")],
            category=snippet.get("categoryId"),
            language=snippet.get("defaultLanguage") or snippet.get("defaultAudioLanguage"),
            country=self.settings.youtube_region,
            published_at=parsed_date,
            duration_seconds=parse_iso8601_duration(content.get("duration")),
            thumbnail_url=thumbnail,
            data_source=source,
            data_confidence=0.95,
            metrics=SourceMetricsIn(
                views=views,
                likes=likes,
                comments=comments,
                engagement_rate=engagement,
                view_velocity=(views / age_hours) if views is not None and age_hours else None,
                engagement_velocity=(((likes or 0) + (comments or 0)) / age_hours) if age_hours else None,
                status_codes={"shares": "unsupported_by_youtube_data_api", "saves": "unsupported"},
            ),
            raw_response=item,
        )
