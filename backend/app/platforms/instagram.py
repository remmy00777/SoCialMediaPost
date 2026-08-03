from __future__ import annotations

import hashlib
import re
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

    def discover_creators(
        self,
        *,
        ig_user_id: str,
        access_token: str,
        hashtags: list[str] | None = None,
        usernames: list[str] | None = None,
        max_creators: int = 100,
        recent_posts_per_creator: int = 10,
    ) -> list[dict[str, Any]]:
        requested = min(max(max_creators, 1), 100)
        candidate_limit = min(max(requested * 2, requested), 200)
        ordered_usernames: list[str] = []

        def add_username(value: str | None) -> None:
            normalized = (value or "").strip().lstrip("@").lower()
            if (
                normalized
                and re.fullmatch(r"[a-z0-9._]+", normalized)
                and normalized not in ordered_usernames
            ):
                ordered_usernames.append(normalized)

        for value in usernames or []:
            add_username(value)

        for hashtag in hashtags or []:
            cleaned = hashtag.strip().lstrip("#")
            if not cleaned:
                continue
            search = self.http.request(
                "GET",
                f"{self.graph_base}/ig_hashtag_search",
                params={
                    "user_id": ig_user_id,
                    "q": cleaned,
                    "access_token": access_token,
                },
            ).json()
            hashtag_ids = [
                str(item.get("id"))
                for item in search.get("data", [])
                if item.get("id")
            ]
            for hashtag_id in hashtag_ids[:1]:
                for edge in ("top_media", "recent_media"):
                    try:
                        media_payload = self.http.request(
                            "GET",
                            f"{self.graph_base}/{hashtag_id}/{edge}",
                            params={
                                "user_id": ig_user_id,
                                "fields": (
                                    "id,caption,comments_count,like_count,media_type,"
                                    "media_product_type,permalink,timestamp,username,"
                                    "thumbnail_url"
                                ),
                                "limit": 50,
                                "access_token": access_token,
                            },
                        ).json()
                    except PlatformAPIError:
                        continue
                    for media in media_payload.get("data", []):
                        add_username(media.get("username"))
                        if len(ordered_usernames) >= candidate_limit:
                            break
                    if len(ordered_usernames) >= candidate_limit:
                        break
            if len(ordered_usernames) >= candidate_limit:
                break

        creators: list[dict[str, Any]] = []
        post_limit = min(max(recent_posts_per_creator, 1), 10)
        for username in ordered_usernames[:candidate_limit]:
            fields = (
                "business_discovery.username(" + username + "){"
                "id,username,name,biography,followers_count,follows_count,"
                "media_count,profile_picture_url,"
                f"media.limit({post_limit})"
                "{id,caption,comments_count,like_count,media_type,"
                "media_product_type,permalink,timestamp,thumbnail_url}"
                "}"
            )
            try:
                payload = self.http.request(
                    "GET",
                    f"{self.graph_base}/{ig_user_id}",
                    params={
                        "fields": fields,
                        "access_token": access_token,
                    },
                ).json()
            except PlatformAPIError:
                continue
            profile = payload.get("business_discovery") or {}
            if not profile.get("id"):
                continue
            followers = (
                int(profile["followers_count"])
                if profile.get("followers_count") is not None
                else None
            )
            recent_posts = [
                self._normalize_business_media(item, profile)
                .model_dump(mode="json")
                for item in (profile.get("media") or {}).get("data", [])
                if item.get("id")
            ]
            creators.append(
                {
                    "platform": "instagram",
                    "external_creator_id": str(profile.get("id")),
                    "username": profile.get("username") or username,
                    "name": profile.get("name")
                    or profile.get("username")
                    or username,
                    "description": profile.get("biography"),
                    "follower_count": followers,
                    "following_count": int(profile.get("follows_count") or 0),
                    "media_count": int(profile.get("media_count") or 0),
                    "profile_url": (
                        "https://www.instagram.com/"
                        f"{profile.get('username') or username}/"
                    ),
                    "thumbnail_url": profile.get("profile_picture_url"),
                    "recent_posts": recent_posts,
                    "latest_content": recent_posts[0] if recent_posts else None,
                    "data_source": "instagram_hashtag_and_business_discovery",
                    "metric_availability": {
                        "followers": "official_business_discovery_metadata",
                        "likes": (
                            "official_business_discovery_media_metadata_when_visible"
                        ),
                        "comments": (
                            "official_business_discovery_media_metadata_when_visible"
                        ),
                        "views": (
                            "not_exposed_for_other_creators_by_business_discovery"
                        ),
                    },
                }
            )
            if len(creators) >= candidate_limit:
                break
        return creators

    def list_creator_posts_by_username(
        self,
        *,
        ig_user_id: str,
        access_token: str,
        username: str,
        limit: int = 5,
    ) -> list[NormalizedVideo]:
        creators = self.discover_creators(
            ig_user_id=ig_user_id,
            access_token=access_token,
            usernames=[username],
            hashtags=[],
            max_creators=1,
            recent_posts_per_creator=min(max(limit, 1), 10),
        )
        if not creators:
            raise PlatformAPIError(
                "Instagram professional creator was not found or Business "
                "Discovery access is unavailable"
            )
        return [
            NormalizedVideo.model_validate(item)
            for item in creators[0].get("recent_posts", [])
        ]

    def _normalize_business_media(
        self,
        item: dict[str, Any],
        profile: dict[str, Any],
    ) -> NormalizedVideo:
        published = item.get("timestamp")
        parsed = (
            datetime.fromisoformat(published.replace("Z", "+00:00"))
            if published
            else None
        )
        followers = (
            int(profile["followers_count"])
            if profile.get("followers_count") is not None
            else None
        )
        likes = (
            int(item["like_count"])
            if item.get("like_count") is not None
            else None
        )
        comments = (
            int(item["comments_count"])
            if item.get("comments_count") is not None
            else None
        )
        caption = item.get("caption") or ""
        return NormalizedVideo(
            platform="instagram",
            external_video_id=str(item["id"]),
            canonical_url=item.get("permalink") or "",
            creator_external_id=str(profile.get("id")),
            creator_name=profile.get("username") or profile.get("name"),
            creator_follower_count=followers,
            title=caption.splitlines()[0][:200] if caption else None,
            caption=caption or None,
            published_at=parsed,
            thumbnail_url=item.get("thumbnail_url"),
            data_source="instagram_business_discovery",
            data_confidence=0.78,
            metrics=SourceMetricsIn(
                views=None,
                likes=likes,
                comments=comments,
                engagement_rate=(
                    ((likes or 0) + (comments or 0)) / followers
                    if followers
                    else None
                ),
                status_codes={
                    "views": "not_exposed_for_other_creator_media",
                    "likes": "available_when_visible",
                    "comments": "available_when_visible",
                },
            ),
            raw_response=item,
        )


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
