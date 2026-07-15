"""Resume-to-job matching: one LLM call extracts job details AND scores the fit."""

import json

from .. import llm, prompts

_CATEGORY_BANDS = [(0.85, "strong"), (0.70, "good"), (0.55, "maybe"), (0.0, "weak")]


def _category_for(score: float) -> str:
    for threshold, name in _CATEGORY_BANDS:
        if score >= threshold:
            return name
    return "weak"


def match_job(profile_data: dict, posting_meta: dict, description_text: str) -> dict:
    """Return the JOB_MATCH_SCHEMA dict, with score/category/recommendation normalized."""
    user = (
        "CANDIDATE PROFILE (JSON extracted from their resume):\n"
        + json.dumps(profile_data, indent=1)
        + "\n\nJOB POSTING METADATA (from the careers page listing):\n"
        + json.dumps(posting_meta, indent=1)
        + "\n\nJOB POSTING TEXT:\n"
        + description_text[:40000]
    )
    result = llm.structured(prompts.JOB_MATCH_SYSTEM, user, prompts.JOB_MATCH_SCHEMA, max_tokens=8192)

    # Normalize: clamp the score and keep category/recommendation consistent with it.
    score = result.get("fit_score")
    score = max(0.0, min(1.0, float(score))) if isinstance(score, (int, float)) else 0.0
    result["fit_score"] = round(score, 2)
    result["fit_category"] = _category_for(score)
    if result.get("recommendation") == "apply" and result["fit_category"] not in ("strong", "good"):
        result["recommendation"] = "maybe" if result["fit_category"] == "maybe" else "skip"
    return result
