"""AI-powered planning phase: examines a PR and produces a ReviewPlan."""

from __future__ import annotations

import logging

from code_review_agent.ai.base import AIProvider
from code_review_agent.ai.prompts import PromptRenderer
from code_review_agent.config import ReviewConfig
from code_review_agent.diff_parser import detect_languages
from code_review_agent.models import AnalyzerType, PRInfo, ReviewPlan

logger = logging.getLogger(__name__)


async def create_review_plan(
    pr: PRInfo,
    config: ReviewConfig,
    ai: AIProvider,
    prompts: PromptRenderer,
) -> ReviewPlan:
    """Run the planning phase and return a ReviewPlan.

    The planner sends PR metadata to the AI, which determines:
    - Which languages are involved
    - Which focus areas matter most for this PR
    - Which files deserve priority attention
    - Which analyzers to run

    The plan is logged so operators can see WHY the agent focused on what it did.
    """
    languages = detect_languages(pr.diff_files)
    total_additions = sum(f.additions for f in pr.diff_files)
    total_deletions = sum(f.deletions for f in pr.diff_files)

    prompt_text = prompts.render(
        "planning.md.j2",
        pr_title=pr.title,
        pr_author=pr.author,
        pr_description=pr.description,
        files=pr.diff_files,
        total_additions=total_additions,
        total_deletions=total_deletions,
        languages=languages,
        custom_instructions=config.custom_instructions,
        configured_focus_areas=config.focus_areas,
    )

    logger.info("Running planning phase for PR #%d (%d files)", pr.number, len(pr.diff_files))

    result = await ai.chat_json(
        messages=[{"role": "user", "content": prompt_text}],
        temperature=config.ai.temperature,
        max_tokens=1024,
    )

    if "error" in result:
        logger.warning("Planning AI returned an error, using defaults: %s", result.get("error"))
        return _default_plan(pr, config, languages)

    plan = _parse_plan(result, languages)

    logger.info(
        "Review plan: focus=%s, analyzers=%s, priority_files=%d, reasoning=%s",
        plan.focus_areas,
        [a.value for a in plan.analyzers_to_run],
        len(plan.priority_files),
        plan.reasoning[:120],
    )

    return plan


def _parse_plan(data: dict, fallback_languages: list[str]) -> ReviewPlan:
    """Parse the AI's JSON response into a ReviewPlan, with fallbacks."""
    analyzers_raw = data.get("analyzers_to_run", ["ai", "linter"])
    analyzers: list[AnalyzerType] = []
    for a in analyzers_raw:
        try:
            analyzers.append(AnalyzerType(a))
        except ValueError:
            logger.warning("Unknown analyzer type from planner: %s", a)

    return ReviewPlan(
        languages=data.get("languages", fallback_languages),
        focus_areas=data.get("focus_areas", ["correctness"]),
        priority_files=data.get("priority_files", []),
        analyzers_to_run=analyzers or [AnalyzerType.AI, AnalyzerType.LINTER],
        reasoning=data.get("reasoning", ""),
        estimated_complexity=data.get("estimated_complexity", "medium"),
    )


def _default_plan(
    pr: PRInfo, config: ReviewConfig, languages: list[str]
) -> ReviewPlan:
    """Fallback plan when the AI fails to produce one."""
    return ReviewPlan(
        languages=languages,
        focus_areas=config.focus_areas,
        priority_files=[f.path for f in pr.diff_files[:5]],
        analyzers_to_run=[AnalyzerType.AI, AnalyzerType.LINTER],
        reasoning="Default plan (AI planning failed or was skipped).",
        estimated_complexity="medium",
    )
