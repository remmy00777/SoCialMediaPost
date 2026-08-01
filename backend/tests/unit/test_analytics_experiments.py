from app.services.analytics import multi_objective_performance, normalized_post_metrics, per_thousand
from app.services.experiments import deterministic_assignment, evaluate_experiment, proportion_confidence_interval


def test_per_thousand_and_normalization():
    assert per_thousand(50, 1000) == 50
    result = normalized_post_metrics({"views": 1000, "likes": 100, "comments": 10, "shares": 20, "saves": 30, "follows": 5, "average_view_duration": 8, "duration": 10}, followers=500)
    assert result["views_per_1000_followers"] == 2000
    assert result["completion_rate_index"] == 0.8


def test_multi_objective_penalizes_warnings():
    good = multi_objective_performance({"completion_rate": 0.8, "retention": 0.8, "shares_per_1000_views": 20, "topic_relevance": 1})
    risky = multi_objective_performance({"completion_rate": 0.8, "retention": 0.8, "shares_per_1000_views": 20, "topic_relevance": 1, "policy_warnings": 1})
    assert risky < good


def test_assignment_is_deterministic():
    assert deterministic_assignment("exp", "package") == deterministic_assignment("exp", "package")


def test_experiment_waits_for_sample_and_can_adopt():
    assert evaluate_experiment([1], [2], 5)["decision"] == "continue"
    result = evaluate_experiment([1.0] * 10, [1.2] * 10, 10)
    assert result["decision"] == "adopt_variant"


def test_confidence_interval_bounds():
    interval = proportion_confidence_interval(50, 100)
    assert 0 <= interval["lower"] < interval["upper"] <= 1
