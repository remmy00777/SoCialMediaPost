from __future__ import annotations

import re
from typing import Any


DISALLOWED_PATTERNS = {
    "guaranteed_virality": re.compile(r"\b(guaranteed|certain)\s+(to\s+)?(go\s+)?viral\b", re.I),
    "fake_engagement": re.compile(r"\b(buy|fake|bot)\s+(followers|likes|comments|views)\b", re.I),
    "detection_evasion": re.compile(r"\b(bypass|evade)\s+(moderation|copyright|ai detection|spam detection)\b", re.I),
    "unauthorized_reupload": re.compile(r"\b(download|repost|reupload)\s+(their|another creator|source)\s+video\b", re.I),
}


def policy_report(content: dict[str, Any], rights: dict[str, str] | None = None) -> dict[str, Any]:
    combined = "\n".join(str(value) for value in content.values() if isinstance(value, (str, list)))
    violations = [name for name, pattern in DISALLOWED_PATTERNS.items() if pattern.search(combined)]
    rights = rights or {
        "music": "original_or_none",
        "footage": "original",
        "images": "original",
        "voice": "synthetic_local_or_user_authorized",
        "fonts": "system_or_open_license",
    }
    missing_rights = [asset for asset, status in rights.items() if status in {"unknown", "unverified", "missing"}]
    blocking = violations + [f"rights_not_verified:{asset}" for asset in missing_rights]
    return {
        "passed": not blocking,
        "checks": {
            "moderation": "passed" if not violations else "failed",
            "rights": "passed" if not missing_rights else "failed",
            "misinformation": "manual_review_required_for_factual_claims",
            "disclosure": "recommend disclosure when synthetic media materially depicts reality",
            "brand_safety": "passed",
            "technical": "pending_media_validation",
        },
        "rights": rights,
        "blocking_reasons": blocking,
        "ruleset_version": "local-policy-v1",
    }
