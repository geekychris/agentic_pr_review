"""Posts review results to GitHub as PR reviews with inline comments."""

from __future__ import annotations

import logging
from typing import Any

from code_review_agent.github_client import GitHubClient
from code_review_agent.models import Finding, PRInfo, ReviewResult, Severity

logger = logging.getLogger(__name__)

SEVERITY_EMOJI = {
    Severity.ERROR: "🔴",
    Severity.WARNING: "🟡",
    Severity.SUGGESTION: "🔵",
    Severity.INFO: "INFO",
}


class Reporter:
    """Converts ReviewResult into GitHub API calls."""

    def __init__(self, gh: GitHubClient) -> None:
        self._gh = gh

    async def post_review(self, pr: PRInfo, result: ReviewResult) -> None:
        """Post the full review to GitHub.

        Creates a single PR review with:
        - Inline comments for each finding (with code suggestions where applicable)
        - A summary body with finding counts
        """
        if not result.findings:
            # Post a clean summary comment
            await self._gh.post_comment(pr.owner, pr.repo, pr.number, result.summary)
            return

        # Build inline comments
        comments = []
        for finding in result.findings:
            comment = self._build_inline_comment(finding, pr)
            if comment:
                comments.append(comment)

        # Determine review event
        event = "COMMENT"
        if result.has_errors:
            event = "REQUEST_CHANGES"

        # GitHub API limits to 50 comments per review
        # If we have more, batch them
        if len(comments) <= 50:
            await self._post_single_review(pr, result.summary, event, comments)
        else:
            await self._post_batched_reviews(pr, result.summary, event, comments)

    async def _post_single_review(
        self,
        pr: PRInfo,
        summary: str,
        event: str,
        comments: list[dict[str, Any]],
    ) -> None:
        """Post a single review with all comments."""
        try:
            await self._gh.create_review(
                owner=pr.owner,
                repo=pr.repo,
                pr_number=pr.number,
                commit_sha=pr.head_sha,
                body=summary,
                event=event,
                comments=comments,
            )
            logger.info("Posted review with %d inline comments", len(comments))
        except Exception:
            logger.exception("Failed to post review, falling back to comment")
            # Fallback: post as a regular comment
            body = summary + "\n\n" + self._findings_as_markdown(comments)
            await self._gh.post_comment(pr.owner, pr.repo, pr.number, body)

    async def _post_batched_reviews(
        self,
        pr: PRInfo,
        summary: str,
        event: str,
        comments: list[dict[str, Any]],
    ) -> None:
        """Post multiple reviews when comments exceed GitHub's 50-comment limit."""
        batch_size = 50
        for i in range(0, len(comments), batch_size):
            batch = comments[i : i + batch_size]
            batch_event = event if i == 0 else "COMMENT"
            batch_body = summary if i == 0 else f"_Continued review ({i + 1}-{i + len(batch)})_"

            try:
                await self._gh.create_review(
                    owner=pr.owner,
                    repo=pr.repo,
                    pr_number=pr.number,
                    commit_sha=pr.head_sha,
                    body=batch_body,
                    event=batch_event,
                    comments=batch,
                )
            except Exception:
                logger.exception("Failed to post review batch starting at %d", i)

    def _build_inline_comment(
        self, finding: Finding, pr: PRInfo
    ) -> dict[str, Any] | None:
        """Convert a Finding into a GitHub review comment dict."""
        # Find the diff file and position
        diff_file = next((f for f in pr.diff_files if f.path == finding.file), None)
        if diff_file is None:
            logger.warning("Finding references unknown file: %s", finding.file)
            return None

        # Build comment body
        emoji = SEVERITY_EMOJI.get(finding.severity, "")
        body_parts = [
            f"**{emoji} {finding.severity.value.upper()}: {finding.title}**",
            "",
            finding.description,
        ]

        # Add code suggestion using GitHub's suggestion syntax
        if finding.suggestion:
            body_parts.extend([
                "",
                "```suggestion",
                finding.suggestion,
                "```",
            ])

        body_parts.append(f"\n_[{finding.analyzer}]_")

        comment: dict[str, Any] = {
            "path": finding.file,
            "body": "\n".join(body_parts),
            "line": finding.line,
            "side": "RIGHT",
        }

        # Multi-line comment
        if finding.end_line and finding.end_line != finding.line:
            comment["start_line"] = finding.line
            comment["start_side"] = "RIGHT"
            comment["line"] = finding.end_line

        return comment

    @staticmethod
    def _findings_as_markdown(comments: list[dict[str, Any]]) -> str:
        """Format findings as markdown (fallback when review API fails)."""
        lines = ["### Detailed Findings\n"]
        for c in comments:
            lines.append(f"**{c['path']}:{c.get('line', '?')}**")
            lines.append(c["body"])
            lines.append("")
        return "\n".join(lines)
