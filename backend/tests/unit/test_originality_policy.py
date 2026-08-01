from app.services.originality import cosine_similarity, originality_report
from app.services.policy import policy_report


def test_original_content_passes():
    source = {"title": "A cat jumps over a box", "caption": "Funny cat", "hashtags": ["#cat"]}
    generated = {"title": "Three questions for choosing software", "caption": "A practical framework", "script": "Define the decision, inspect evidence, choose an action.", "hashtags": ["#software"]}
    report = originality_report(generated, source)
    assert report["passed"]


def test_near_copy_is_blocked():
    source = {"title": "Three ways to choose a laptop", "caption": "Three ways to choose a laptop", "transcript": "first check cost then battery then screen quality", "hashtags": ["#laptop"]}
    generated = {"title": "Three ways to choose a laptop", "caption": "Three ways to choose a laptop", "script": "first check cost then battery then screen quality", "hashtags": ["#laptop"]}
    report = originality_report(generated, source)
    assert not report["passed"]
    assert report["blocking_reasons"]


def test_policy_blocks_guaranteed_virality():
    report = policy_report({"script": "This is guaranteed to go viral."})
    assert not report["passed"]
    assert "guaranteed_virality" in report["blocking_reasons"]


def test_policy_requires_rights():
    report = policy_report({"script": "Original text"}, rights={"music": "unknown"})
    assert not report["passed"]
