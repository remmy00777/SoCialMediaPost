from __future__ import annotations

from app.platforms.base import PlatformAdapter
from app.platforms.instagram import InstagramAdapter
from app.platforms.tiktok import TikTokAdapter
from app.platforms.youtube import YouTubeAdapter


class PlatformRegistry:
    def __init__(self) -> None:
        self._adapters: dict[str, PlatformAdapter] = {
            "youtube": YouTubeAdapter(),
            "tiktok": TikTokAdapter(),
            "instagram": InstagramAdapter(),
        }

    def get(self, platform: str) -> PlatformAdapter:
        try:
            return self._adapters[platform.lower()]
        except KeyError as exc:
            raise ValueError(f"Unsupported platform: {platform}") from exc

    def all(self) -> list[PlatformAdapter]:
        return list(self._adapters.values())


registry = PlatformRegistry()
