from pathlib import Path

import pytest

from app.core.config import Settings
from app.platforms.instagram import InstagramAdapter, parse_instagram_id
from app.platforms.tiktok import TikTokAdapter, parse_tiktok_id
from app.platforms.youtube import YouTubeAdapter, parse_iso8601_duration, parse_youtube_id


def settings(tmp_path: Path) -> Settings:
    return Settings(storage_root=tmp_path, session_secret="x" * 32)


def test_url_parsers():
    assert parse_youtube_id("https://youtu.be/abc123") == "abc123"
    assert parse_youtube_id("https://www.youtube.com/shorts/xyz") == "xyz"
    assert parse_tiktok_id("https://www.tiktok.com/@a/video/123") == "123"
    assert parse_instagram_id("https://www.instagram.com/reel/ABC/") == "ABC"


def test_duration_parser():
    assert parse_iso8601_duration("PT1H2M3S") == 3723
    assert parse_iso8601_duration(None) is None


def test_health_reports_limitations(tmp_path: Path):
    for adapter in [YouTubeAdapter(settings(tmp_path)), TikTokAdapter(settings(tmp_path)), InstagramAdapter(settings(tmp_path))]:
        health = adapter.health_check()
        assert health.platform
        assert health.limitations
        assert not health.configured


def test_manual_import_never_scrapes(tmp_path: Path):
    video = TikTokAdapter(settings(tmp_path)).import_video_reference("https://www.tiktok.com/@a/video/123")
    assert video.data_source == "manual_url_import"
    assert video.metrics.views is None
