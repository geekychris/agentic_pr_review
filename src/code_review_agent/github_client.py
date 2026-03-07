"""Async GitHub REST API client for PR operations."""

from __future__ import annotations

import base64
import logging
from typing import Any

import httpx

from code_review_agent.config import CONFIG_FILENAME
from code_review_agent.diff_parser import parse_diff
from code_review_agent.models import FileContent, PRInfo

logger = logging.getLogger(__name__)

API_BASE = "https://api.github.com"


class GitHubClient:
    """Thin async wrapper around the GitHub REST API for PR review operations."""

    def __init__(self, token: str) -> None:
        self._token = token
        self._client = httpx.AsyncClient(
            base_url=API_BASE,
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/vnd.github.v3+json",
                "X-GitHub-Api-Version": "2022-11-28",
            },
            timeout=60.0,
        )

    async def close(self) -> None:
        await self._client.aclose()

    async def __aenter__(self) -> GitHubClient:
        return self

    async def __aexit__(self, *exc: object) -> None:
        await self.close()

    # ------------------------------------------------------------------
    # PR metadata
    # ------------------------------------------------------------------

    async def get_pr(self, owner: str, repo: str, pr_number: int) -> PRInfo:
        """Fetch PR metadata and diff, returning a fully populated PRInfo."""
        # Fetch PR JSON
        resp = await self._client.get(f"/repos/{owner}/{repo}/pulls/{pr_number}")
        resp.raise_for_status()
        pr_data = resp.json()

        # Fetch raw diff
        diff_resp = await self._client.get(
            f"/repos/{owner}/{repo}/pulls/{pr_number}",
            headers={"Accept": "application/vnd.github.v3.diff"},
        )
        diff_resp.raise_for_status()
        raw_diff = diff_resp.text

        diff_files = parse_diff(raw_diff)

        return PRInfo(
            owner=owner,
            repo=repo,
            number=pr_number,
            title=pr_data.get("title", ""),
            description=pr_data.get("body", "") or "",
            base_sha=pr_data["base"]["sha"],
            head_sha=pr_data["head"]["sha"],
            base_ref=pr_data["base"]["ref"],
            head_ref=pr_data["head"]["ref"],
            author=pr_data["user"]["login"],
            diff_files=diff_files,
            raw_diff=raw_diff,
        )

    # ------------------------------------------------------------------
    # File contents
    # ------------------------------------------------------------------

    async def get_file_content(
        self, owner: str, repo: str, path: str, ref: str
    ) -> FileContent | None:
        """Fetch the full content of a file at a given ref."""
        resp = await self._client.get(
            f"/repos/{owner}/{repo}/contents/{path}",
            params={"ref": ref},
        )
        if resp.status_code == 404:
            return None
        resp.raise_for_status()
        data = resp.json()
        content = base64.b64decode(data["content"]).decode("utf-8", errors="replace")
        return FileContent(path=path, content=content, ref=ref)

    async def get_repo_config(self, owner: str, repo: str, ref: str) -> str | None:
        """Try to fetch .codereview.yml from the repo."""
        fc = await self.get_file_content(owner, repo, CONFIG_FILENAME, ref)
        return fc.content if fc else None

    # ------------------------------------------------------------------
    # Posting reviews
    # ------------------------------------------------------------------

    async def create_review(
        self,
        owner: str,
        repo: str,
        pr_number: int,
        commit_sha: str,
        body: str,
        event: str = "COMMENT",
        comments: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        """Create a pull request review with optional inline comments.

        Parameters
        ----------
        event : str
            One of APPROVE, REQUEST_CHANGES, COMMENT
        comments : list
            Each dict should have: path, line, side, body.
            Optionally start_line + start_side for multi-line comments.
        """
        payload: dict[str, Any] = {
            "commit_id": commit_sha,
            "body": body,
            "event": event,
        }
        if comments:
            payload["comments"] = comments

        resp = await self._client.post(
            f"/repos/{owner}/{repo}/pulls/{pr_number}/reviews",
            json=payload,
        )
        if resp.status_code >= 400:
            logger.error(
                "GitHub review API error %d: %s",
                resp.status_code,
                resp.text,
            )
        resp.raise_for_status()
        return resp.json()

    async def post_comment(
        self, owner: str, repo: str, pr_number: int, body: str
    ) -> dict[str, Any]:
        """Post a top-level issue comment on the PR."""
        resp = await self._client.post(
            f"/repos/{owner}/{repo}/issues/{pr_number}/comments",
            json={"body": body},
        )
        resp.raise_for_status()
        return resp.json()

    # ------------------------------------------------------------------
    # Issues (for the test harness)
    # ------------------------------------------------------------------

    async def create_issue(
        self, owner: str, repo: str, title: str, body: str, labels: list[str] | None = None
    ) -> dict[str, Any]:
        """Create a GitHub issue."""
        payload: dict[str, Any] = {"title": title, "body": body}
        if labels:
            payload["labels"] = labels
        resp = await self._client.post(
            f"/repos/{owner}/{repo}/issues",
            json=payload,
        )
        resp.raise_for_status()
        return resp.json()

    # ------------------------------------------------------------------
    # Branch / PR creation (for test harness)
    # ------------------------------------------------------------------

    async def get_ref_sha(self, owner: str, repo: str, ref: str = "heads/main") -> str:
        """Get the SHA of a git ref."""
        resp = await self._client.get(f"/repos/{owner}/{repo}/git/ref/{ref}")
        resp.raise_for_status()
        return resp.json()["object"]["sha"]

    async def create_branch(
        self, owner: str, repo: str, branch_name: str, from_sha: str
    ) -> None:
        """Create a new branch from a SHA."""
        resp = await self._client.post(
            f"/repos/{owner}/{repo}/git/refs",
            json={"ref": f"refs/heads/{branch_name}", "sha": from_sha},
        )
        resp.raise_for_status()

    async def create_or_update_file(
        self,
        owner: str,
        repo: str,
        path: str,
        content: str,
        message: str,
        branch: str,
        sha: str | None = None,
    ) -> dict[str, Any]:
        """Create or update a file in the repo."""
        payload: dict[str, Any] = {
            "message": message,
            "content": base64.b64encode(content.encode()).decode(),
            "branch": branch,
        }
        if sha:
            payload["sha"] = sha
        resp = await self._client.put(
            f"/repos/{owner}/{repo}/contents/{path}",
            json=payload,
        )
        resp.raise_for_status()
        return resp.json()

    async def create_pull_request(
        self,
        owner: str,
        repo: str,
        title: str,
        body: str,
        head: str,
        base: str = "main",
    ) -> dict[str, Any]:
        """Create a pull request."""
        resp = await self._client.post(
            f"/repos/{owner}/{repo}/pulls",
            json={"title": title, "body": body, "head": head, "base": base},
        )
        resp.raise_for_status()
        return resp.json()
