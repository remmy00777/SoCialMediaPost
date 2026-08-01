from __future__ import annotations

import re
from collections import Counter
from typing import Any


DEFAULT_THRESHOLDS = {
    "script_similarity": 0.42,
    "caption_similarity": 0.50,
    "title_similarity": 0.55,
    "hashtag_overlap": 0.65,
    "distinctive_phrase_overlap": 0.25,
}


def tokens(text: str) -> list[str]:
    return [item.lower() for item in re.findall(r"[A-Za-z0-9']+", text) if len(item) > 2]


def cosine_similarity(left: str, right: str) -> float:
    a = Counter(tokens(left))
    b = Counter(tokens(right))
    if not a or not b:
        return 0.0
    dot = sum(a[key] * b[key] for key in a.keys() & b.keys())
    mag_a = sum(value * value for value in a.values()) ** 0.5
    mag_b = sum(value * value for value in b.values()) ** 0.5
    return dot / (mag_a * mag_b) if mag_a and mag_b else 0.0


def ngrams(text: str, n: int = 5) -> set[tuple[str, ...]]:
    words = tokens(text)
    return {tuple(words[index : index + n]) for index in range(max(len(words) - n + 1, 0))}


def originality_report(
    generated: dict[str, Any], source: dict[str, Any], thresholds: dict[str, float] | None = None
) -> dict[str, Any]:
    limits = thresholds or DEFAULT_THRESHOLDS
    source_script = source.get("transcript") or source.get("caption") or source.get("title") or ""
    source_caption = source.get("caption") or ""
    source_title = source.get("title") or ""
    generated_script = generated.get("script") or ""
    generated_caption = generated.get("caption") or ""
    generated_title = generated.get("title") or ""
    source_tags = {tag.lower() for tag in source.get("hashtags", [])}
    generated_tags = {tag.lower() for tag in generated.get("hashtags", [])}
    phrase_left = ngrams(source_script)
    phrase_right = ngrams(generated_script)
    phrase_overlap = len(phrase_left & phrase_right) / max(len(phrase_left), 1)
    scores = {
        "script_similarity": cosine_similarity(generated_script, source_script),
        "caption_similarity": cosine_similarity(generated_caption, source_caption),
        "title_similarity": cosine_similarity(generated_title, source_title),
        "hashtag_overlap": len(source_tags & generated_tags) / max(len(source_tags), 1),
        "distinctive_phrase_overlap": phrase_overlap,
    }
    blocking = [key for key, value in scores.items() if value > limits[key]]
    return {
        "passed": not blocking,
        "component_scores": {key: round(value, 4) for key, value in scores.items()},
        "thresholds": limits,
        "blocking_reasons": [f"{key} exceeded its threshold" for key in blocking],
        "principle": "The system learns structural patterns but does not reproduce protected expression.",
    }
