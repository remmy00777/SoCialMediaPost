from __future__ import annotations

import hashlib
import random
from dataclasses import dataclass
from typing import Any


@dataclass(slots=True)
class BrandContext:
    name: str
    niche: str
    target_audience: str
    brand_voice: str
    topics_exclude: list[str]
    preferred_duration_seconds: int


class LocalTemplateProvider:
    """Deterministic local fallback that creates editable packages without paid APIs."""

    version = "local-template-v1"

    def analyze_trend(self, source: dict[str, Any]) -> dict[str, Any]:
        title = source.get("title") or source.get("caption") or "Untitled trend"
        topic = source.get("topic") or self._topic_from_text(title)
        observations = {
            "plain_language_summary": f"A {source.get('platform', 'social')} video about {topic} is receiving measurable attention.",
            "topic": topic,
            "subtopic": title[:120],
            "opening_hook": "The content makes its value clear before asking for sustained attention.",
            "first_three_second_structure": "Immediate claim, visual change, and open question.",
            "story_structure": "Hook, concise context, useful payoff, audience prompt.",
            "pacing": "Fast opening followed by short information blocks.",
            "scene_progression": "Problem, evidence, practical takeaway.",
            "editing_rhythm": "Frequent but readable changes every two to four seconds.",
            "visual_pattern": "Single focal subject with large safe-area text.",
            "text_overlay_pattern": "One short idea per screen.",
            "audio_role": "Supports pacing without carrying essential facts.",
            "caption_strategy": "Searchable summary plus a direct question.",
            "hashtag_strategy": "Small set of topic-specific tags rather than generic reach tags.",
            "call_to_action_strategy": "Invite a useful opinion or experience.",
            "rewatch_mechanism": "Dense but clear information that rewards a second pass.",
            "loop_structure": "Closing question reconnects to the opening claim.",
        }
        interpretations = {
            "intended_audience": "People already interested in the topic and adjacent practical questions.",
            "viewer_motivation": "Learn something quickly and decide whether it applies to them.",
            "emotional_drivers": ["curiosity", "usefulness", "recognition"],
            "curiosity_mechanism": "An unresolved opening claim with a concrete payoff.",
            "comment_driving_mechanism": "A specific, answerable question.",
            "share_driving_mechanism": "Practical information that is easy to send to one person.",
            "cultural_context": "Requires human review when references depend on current events or local meaning.",
            "timeliness": "Potentially time-sensitive, based on retrieval recency.",
            "potential_weaknesses": ["The source may rely on creator familiarity", "The topic may already be saturating"],
            "oversaturation_risk": "medium",
            "copyright_risk": "medium until source assets are excluded from generation",
            "misinformation_risk": "manual fact review required for factual claims",
            "brand_safety_risk": "low based on available metadata",
            "replication_risk": "controlled by originality thresholds",
            "opportunity_for_original_improvement": "Add a clearer practical framework and stronger audience-specific examples.",
            "recommended_creative_angle": f"Explain {topic} through a new three-part decision framework.",
            "evidence_supporting_recommendation": [
                "The source exposes an identifiable topic and opening promise.",
                "Short-form audiences generally benefit from clear information hierarchy.",
                "The proposed angle does not depend on copying source footage or wording.",
            ],
        }
        return {
            "observations": observations,
            "interpretations": interpretations,
            "confidence": 0.68,
            "supporting_signals": ["metadata", "engagement metrics when available", "publication recency"],
            "missing_information": ["full visual sequence", "complete audio context", "viewer retention curve"],
            "assumptions": ["The source metadata accurately represents the topic", "No protected expression will be reused"],
        }

    def generate_concepts(
        self, source: dict[str, Any], analysis: dict[str, Any], brand: BrandContext, count: int = 3
    ) -> list[dict[str, Any]]:
        topic = analysis["observations"].get("topic", "the topic")
        angles = [
            ("decision framework", "Turn the topic into a three-question decision guide."),
            ("myth versus reality", "Correct one common misunderstanding with a calm evidence-first explanation."),
            ("practical checklist", "Give the audience a short checklist they can use immediately."),
        ]
        results = []
        for index, (label, angle) in enumerate(angles[:count]):
            scores = {
                "originality": 0.86 - index * 0.03,
                "relevance": 0.88 - index * 0.02,
                "clarity": 0.90 - index * 0.02,
                "emotional_impact": 0.72 + index * 0.03,
                "shareability": 0.78 + index * 0.02,
                "watch_time_potential": 0.79 - index * 0.01,
                "comment_potential": 0.74 + index * 0.03,
                "follow_conversion_potential": 0.70 + index * 0.02,
                "production_feasibility": 0.94,
                "brand_alignment": 0.88,
                "platform_compliance": 0.96,
                "copyright_safety": 0.98,
            }
            total = sum(scores.values()) / len(scores)
            results.append(
                {
                    "status": "candidate",
                    "selected": index == 0,
                    "concept": {
                        "new_angle": angle,
                        "unique_value_proposition": f"A concise {label} tailored to {brand.target_audience}.",
                        "audience_promise": f"Understand {topic} well enough to take one practical next step.",
                        "primary_hook": f"Before you decide what to do about {topic}, answer these three questions.",
                        "alternative_hooks": [
                            f"Most people approach {topic} in the wrong order.",
                            f"This simple framework makes {topic} easier to evaluate.",
                        ],
                        "core_message": f"Use a clear framework instead of copying the reaction that made the source trend popular.",
                        "supporting_points": ["Define the real problem", "Check the strongest evidence", "Choose the next useful action"],
                        "story_arc": "Open loop, three-part framework, practical close.",
                        "emotional_target": "confidence and informed curiosity",
                        "visual_concept": "Original kinetic typography with simple geometric scenes and no source media.",
                        "recommended_duration": brand.preferred_duration_seconds,
                        "call_to_action": "Which of the three questions matters most in your situation?",
                        "platform_adaptation_plan": {
                            "tiktok": "Fastest hook, conversational delivery, looped final question.",
                            "instagram": "Polished cover, save-oriented caption, clean visual rhythm.",
                            "youtube": "Search-led title and a slightly fuller explanation for retention.",
                        },
                        "reasons_it_could_outperform": ["Clearer structure", "More practical value", "Original wording and visuals"],
                        "reasons_it_might_fail": ["Topic demand may fade", "Audience may prefer entertainment over instruction"],
                        "testing_hypothesis": "A three-part framework will increase completion and saves relative to a single-claim format.",
                        "success_metric": "Completion rate and saves per 1,000 views",
                        "confidence": round(0.72 - index * 0.03, 2),
                    },
                    "component_scores": scores,
                    "total_score": round(total * 100, 2),
                    "prompt_version": self.version,
                }
            )
        return results

    def generate_package(self, concept: dict[str, Any], source: dict[str, Any], brand: BrandContext) -> dict[str, Any]:
        topic = source.get("topic") or self._topic_from_text(source.get("title") or source.get("caption") or "this topic")
        source_media = source.get("source_media") or None
        reusable_source = bool(
            source_media
            and source_media.get("allow_full_reuse")
            and source_media.get("rights_status")
            in {"user_owned", "licensed", "public_domain", "explicit_permission"}
        )
        hashtags = self._hashtags(topic, brand.niche)
        seed = int(hashlib.sha256(topic.encode()).hexdigest()[:8], 16)

        if reusable_source:
            validation = source_media.get("media_validation") or {}
            attribution = (
                validation.get("attribution_text")
                or f"Original creator: {source.get('creator_name') or source_media.get('rights_owner')}"
            )
            intro = (
                f"{attribution}. Before you watch this authorized clip about {topic}, "
                "focus on the opening, pacing, and the specific reason it holds attention."
            )
            caption = (
                f"{attribution}. Authorized full-source repost with an original voiceover introduction "
                f"about {topic}. Reuse is based on the recorded ownership, license, public-domain, "
                "or permission declaration."
            )
            return {
                "title": f"What Makes This {topic.title()} Clip Work",
                "hook": intro,
                "script": f"{intro}\n\n[The complete authorized source clip plays after the introduction.]",
                "voiceover_text": intro,
                "voiceover_intro": intro,
                "shot_list": [
                    "Opening: Original title card with synthesized voiceover context",
                    "After voiceover: Play the complete authorized source clip",
                    "End: Preserve the source ending unless the license requires attribution",
                ],
                "editing_instructions": (
                    "Prepend an original voiceover introduction, then play the full uploaded source clip. "
                    "Use letterboxing or padding rather than destructive cropping. Do not download media from a platform URL."
                ),
                "on_screen_text": [
                    f"Before you watch: notice what makes this {topic} clip effective",
                    "Authorized source clip follows",
                ],
                "caption": caption,
                "description": caption + "\n\nRights declaration and license reference are stored in the package compliance report.",
                "hashtags": hashtags,
                "keywords": [topic, brand.niche, "authorized clip", "voiceover introduction"],
                "call_to_action": "What part of the clip held your attention most?",
                "content_mode": "authorized_source_with_voiceover_intro",
                "source_media": source_media,
                "generation_metadata": {
                    "provider": "local_template",
                    "provider_version": self.version,
                    "source_media_used": True,
                    "source_rights_status": source_media.get("rights_status"),
                    "source_attribution": attribution,
                    "manual_post_only": True,
                    "paid_api_calls": 0,
                    "seed": seed,
                },
                "predicted_performance_range": {
                    "basis": "heuristic only, not a promise",
                    "relative_to_account_baseline": "0.7x to 1.4x",
                    "confidence": 0.35,
                },
            }

        hook = concept["primary_hook"]
        script = (
            f"{hook}\n\n"
            "First, define the actual decision. A popular video can show demand, but it does not automatically prove the conclusion.\n\n"
            "Second, separate evidence from interpretation. Check what is known, what is missing, and what assumptions are being made.\n\n"
            "Third, choose one useful action that fits your audience, your values, and the facts available now.\n\n"
            f"That is how we turn a trend about {topic} into original value instead of a copy. "
            f"{concept['call_to_action']}"
        )
        base_title = f"A Better Way to Think About {topic.title()}"
        caption = (
            f"A trending idea is only a starting signal. This three-part framework helps you evaluate {topic} "
            "without copying the source or overstating what the data proves. "
            f"{concept['call_to_action']}"
        )
        return {
            "title": base_title,
            "hook": hook,
            "script": script,
            "voiceover_text": script,
            "shot_list": [
                "0-3s: Bold hook over an original moving gradient",
                "3-10s: Question one with animated number and concise text",
                "10-18s: Question two with evidence versus interpretation split",
                "18-26s: Question three with action checklist",
                "26-30s: Closing question and subtle loop back to the hook",
            ],
            "editing_instructions": "Use original geometric backgrounds, two-to-four-second scene changes, safe-area text, and no source footage.",
            "on_screen_text": [hook, "1. Define the decision", "2. Separate evidence", "3. Choose one useful action", concept["call_to_action"]],
            "caption": caption,
            "description": caption + "\n\nCreated from high-level trend patterns using original script and visuals.",
            "hashtags": hashtags,
            "keywords": [topic, brand.niche, "decision framework", "practical guide"],
            "call_to_action": concept["call_to_action"],
            "content_mode": "original_generation",
            "source_media": None,
            "generation_metadata": {
                "provider": "local_template",
                "provider_version": self.version,
                "source_media_used": False,
                "paid_api_calls": 0,
                "seed": seed,
            },
            "predicted_performance_range": {
                "basis": "heuristic only, not a promise",
                "relative_to_account_baseline": "0.7x to 1.4x",
                "confidence": 0.35,
            },
        }

    def adapt_platform(self, package: dict[str, Any], platform: str) -> dict[str, Any]:
        if package.get("content_mode") == "authorized_source_with_voiceover_intro":
            platform_names = {"tiktok": "TikTok", "instagram": "Instagram Reels", "youtube": "YouTube"}
            post_settings: dict[str, Any]
            if platform == "tiktok":
                post_settings = {"privacy_level": "SELF_ONLY", "allow_comments": True, "allow_duet": False, "allow_stitch": False}
            elif platform == "instagram":
                post_settings = {"share_to_feed": True, "comments_enabled": True}
            else:
                post_settings = {"privacy_setting": "private", "made_for_kids": False}
            return {
                **package,
                "platform": platform,
                "title": f"{package['title']} | {platform_names[platform]}",
                "caption": package["caption"] + f"\n\nPrepared for {platform_names[platform]}.",
                "post_settings": post_settings,
                "content_disclosure_recommendation": "Disclose synthetic voiceover and provide source attribution when required by the license.",
                "recommended_publishing_window": "Use account analytics to test the best audience window.",
            }
        base_script = package["script"]
        if platform == "tiktok":
            hook = "Stop copying trends. Ask these three questions first."
            call_to_action = "Which question would you answer first, one, two, or three?"
            return {
                **package,
                "platform": "tiktok",
                "title": "3 Questions Before You Follow a Trend",
                "hook": hook,
                "script": f"{hook}\n\n{base_script.split(chr(10) + chr(10), 1)[-1]}\n\n{call_to_action}",
                "voiceover_text": f"{hook} {package['voiceover_text']} {call_to_action}",
                "on_screen_text": [
                    hook,
                    "1. Define the real decision",
                    "2. Separate facts from assumptions",
                    "3. Choose one useful action",
                    "Comment 1, 2, or 3",
                ],
                "call_to_action": call_to_action,
                "caption": (package["caption"] + " Comment 1, 2, or 3 with your answer.")[:1800],
                "hashtags": package["hashtags"][:6],
                "post_settings": {"privacy_level": "SELF_ONLY", "allow_comments": True, "allow_duet": False, "allow_stitch": False},
                "content_disclosure_recommendation": "Enable synthetic-media disclosure when required by the final assets.",
                "recommended_publishing_window": "Test 6:00 PM to 9:00 PM in the audience timezone.",
            }
        if platform == "instagram":
            hook = "Save this before you build your next post from a trend."
            call_to_action = "Save this framework, then share it with someone planning their next Reel."
            return {
                **package,
                "platform": "instagram",
                "title": "The 3-Step Originality Framework",
                "hook": hook,
                "script": f"{hook}\n\n{base_script.split(chr(10) + chr(10), 1)[-1]}\n\n{call_to_action}",
                "voiceover_text": f"{hook} {package['voiceover_text']} {call_to_action}",
                "on_screen_text": [
                    hook,
                    "Define the decision",
                    "Check facts versus interpretation",
                    "Create one original takeaway",
                    "Save this framework",
                ],
                "call_to_action": call_to_action,
                "caption": package["caption"] + "\n\nSave this framework for the next trend you evaluate.",
                "hashtags": package["hashtags"][:8],
                "alt_text_recommendation": "Animated three-part framework explaining how to evaluate a trending idea.",
                "post_settings": {"share_to_feed": True, "comments_enabled": True},
                "recommended_publishing_window": "Test 11:00 AM to 1:00 PM or 6:00 PM to 8:00 PM.",
            }
        hook = "How do you turn a trend into original value? Use this three-question framework."
        call_to_action = "Which content framework should I break down next?"
        return {
            **package,
            "platform": "youtube",
            "format": "short",
            "hook": hook,
            "script": f"{hook}\n\n{base_script.split(chr(10) + chr(10), 1)[-1]}\n\n{call_to_action}",
            "voiceover_text": f"{hook} {package['voiceover_text']} {call_to_action}",
            "on_screen_text": [
                hook,
                "Question 1: What is the decision?",
                "Question 2: What does the evidence show?",
                "Question 3: What original value can you add?",
                "Subscribe for the next framework",
            ],
            "call_to_action": call_to_action,
            "title_candidates": [
                "3 Questions to Ask Before Following a Trend",
                "How to Turn a Trend Into Original Value",
                "The 3-Step Framework for Better Social Content",
            ],
            "title": "3 Questions to Ask Before Following a Trend",
            "description": (package["description"] + f"\n\n{call_to_action}")[:5000],
            "tags": package["keywords"][:20],
            "category": "27",
            "audience_settings": {"made_for_kids": False},
            "privacy_setting": "private",
            "end_screen_recommendation": "Link to the next related framework video when available.",
            "recommended_publishing_window": "Test 12:00 PM to 3:00 PM in the audience timezone.",
        }

    @staticmethod
    def _topic_from_text(text: str) -> str:
        words = [word.strip("#.,!?()[]{}") for word in text.split() if len(word.strip("#.,!?()[]{}")) > 4]
        return " ".join(words[:3]).lower() or "the topic"

    @staticmethod
    def _hashtags(topic: str, niche: str) -> list[str]:
        clean = lambda value: "#" + "".join(ch for ch in value.title() if ch.isalnum())
        tags = [clean(topic), clean(niche), "#PracticalFramework", "#OriginalContent", "#LearnOnSocial"]
        return list(dict.fromkeys(tag for tag in tags if len(tag) > 1))
