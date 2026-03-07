"""Create a test PR with intentionally problematic code for end-to-end testing."""

from __future__ import annotations

import logging
import time
from pathlib import Path

from code_review_agent.github_client import GitHubClient

logger = logging.getLogger(__name__)

TEST_FILES_DIR = Path(__file__).parent / "test_files"


async def create_test_pr(owner: str, repo: str, token: str) -> dict:
    """Create a test PR with known issues in the target repository.

    Steps:
    1. Get the SHA of the default branch
    2. Create a new branch: test/code-review-{timestamp}
    3. Add intentionally bad test files
    4. Create a pull request

    Returns the PR data dict from the GitHub API.
    """
    branch_name = f"test/code-review-{int(time.time())}"

    async with GitHubClient(token) as gh:
        # Get base SHA
        base_sha = await gh.get_ref_sha(owner, repo)
        logger.info("Base SHA: %s", base_sha[:8])

        # Create branch
        await gh.create_branch(owner, repo, branch_name, base_sha)
        logger.info("Created branch: %s", branch_name)

        # Add test files
        test_files = _load_test_files()
        for path, content in test_files.items():
            await gh.create_or_update_file(
                owner=owner,
                repo=repo,
                path=path,
                content=content,
                message=f"test: add {path} with known issues",
                branch=branch_name,
            )
            logger.info("Added: %s", path)

        # Create PR
        pr = await gh.create_pull_request(
            owner=owner,
            repo=repo,
            title="[TEST] Code review agent test PR — DO NOT MERGE",
            body=(
                "## Test PR for Code Review Agent\n\n"
                "This PR contains intentionally problematic code to test the "
                "AI code review agent. **Do not merge.**\n\n"
                "### Expected findings:\n"
                "- Python: SQL injection, unused imports, missing error handling\n"
                "- Java: resource leaks, null pointer risks\n"
                "- Go: unchecked errors, race conditions\n"
                "- Rust: unwrap on Result, unsafe blocks\n\n"
                "Created by `code-review-agent test-pr`."
            ),
            head=branch_name,
        )

        pr_url = pr.get("html_url", "")
        logger.info("Created PR: %s", pr_url)
        print(f"\nTest PR created: {pr_url}")
        return pr


def _load_test_files() -> dict[str, str]:
    """Load test files from the test_files directory."""
    files = {}
    for tf in TEST_FILES_DIR.iterdir():
        if tf.is_file() and not tf.name.startswith("_"):
            # Place files under a test_code/ directory in the repo
            target_path = f"test_code/{tf.name}"
            files[target_path] = tf.read_text()
    return files
