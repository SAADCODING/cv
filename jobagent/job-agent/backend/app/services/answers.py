"""Generate truthful, natural written answers for application questions."""

import json

from .. import llm, prompts


def generate_answers(profile: dict, job: dict, questions: list[str]) -> list[dict]:
    if not questions:
        return []
    user = (
        "CANDIDATE PROFILE (JSON from their resume):\n"
        + json.dumps(profile, indent=1)
        + "\n\nJOB:\n"
        + json.dumps(
            {
                "company": job.get("company"),
                "title": job.get("title"),
                "description": (job.get("description") or "")[:8000],
            },
            indent=1,
        )
        + "\n\nQUESTIONS TO ANSWER:\n"
        + "\n".join(f"- {q}" for q in questions)
    )
    result = llm.structured(prompts.ANSWERS_SYSTEM, user, prompts.ANSWERS_SCHEMA, max_tokens=8192)
    return result.get("answers", [])
