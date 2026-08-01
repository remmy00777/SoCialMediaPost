from datetime import UTC, datetime, timedelta

from app.schemas import NormalizedVideo, SourceMetricsIn
from app.services.trend_scoring import TrendScorer, dedupe_key, log_scale


def video(**overrides):
    base = dict(
        platform="youtube",
        external_video_id="1",
        canonical_url="https://youtube.com/watch?v=1",
        title="Useful AI tool evaluation framework",
        topic="AI tools",
        published_at=datetime.now(UTC) - timedelta(hours=4),
        creator_follower_count=10000,
        data_source="test",
        data_confidence=0.9,
        metrics=SourceMetricsIn(views=100000, likes=12000, comments=600, view_velocity=25000, engagement_velocity=3150),
    )
    base.update(overrides)
    return NormalizedVideo(**base)


def test_high_signal_video_scores_well():
    result = TrendScorer().score(video())
    assert 0 <= result.score <= 100
    assert result.score > 55
    assert result.confidence > 0.7
    assert result.explanation


def test_missing_metrics_reduce_confidence():
    complete = TrendScorer().score(video())
    sparse = TrendScorer().score(video(metrics=SourceMetricsIn()))
    assert sparse.confidence < complete.confidence
    assert "views" in sparse.missing_metrics


def test_dedupe_key_uses_content_terms():
    left = video(external_video_id="1")
    right = video(external_video_id="2", platform="tiktok")
    assert dedupe_key(left) == dedupe_key(right)


def test_log_scale_bounds():
    assert log_scale(None, 100) is None
    assert log_scale(0, 100) == 0
    assert log_scale(1000, 100) == 1
