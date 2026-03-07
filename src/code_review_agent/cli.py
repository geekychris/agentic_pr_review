"""CLI interface for the code review agent."""

from __future__ import annotations

import asyncio
import json
import logging
import sys
from typing import Any

import click
from rich.console import Console
from rich.table import Table

from code_review_agent import __version__
from code_review_agent.config import AgentSettings
from code_review_agent.pipeline import run_review

console = Console()


def _setup_logging(debug: bool = False) -> None:
    level = logging.DEBUG if debug else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )


@click.group()
@click.version_option(version=__version__)
def main() -> None:
    """AI-powered code review agent for GitHub pull requests."""


@main.command()
@click.argument("pr_url")
@click.option("--dry-run", is_flag=True, help="Don't post to GitHub, just print findings")
@click.option("--debug", is_flag=True, help="Enable debug logging")
@click.option("--config", "config_path", type=click.Path(), help="Path to local .codereview.yml")
@click.option("--json-output", is_flag=True, help="Output findings as JSON")
@click.option(
    "--severity",
    type=click.Choice(["error", "warning", "suggestion", "info"], case_sensitive=False),
    default=None,
    help="Only report findings at this severity or above (overrides config)",
)
@click.option(
    "--max-comments", type=int, default=None, help="Max total comments (overrides config)"
)
def review(
    pr_url: str,
    dry_run: bool,
    debug: bool,
    config_path: str | None,
    json_output: bool,
    severity: str | None,
    max_comments: int | None,
) -> None:
    """Review a pull request.

    PR_URL should be like: https://github.com/owner/repo/pull/123
    or shorthand: owner/repo#123
    """
    _setup_logging(debug)

    owner, repo, pr_number = _parse_pr_url(pr_url)
    settings = AgentSettings(dry_run=dry_run, debug=debug)

    if not settings.github_token:
        console.print("[red]Error:[/] Set CRA_GITHUB_TOKEN or GITHUB_TOKEN environment variable")
        sys.exit(1)

    config_overrides: dict[str, Any] | None = None
    if config_path:
        from pathlib import Path

        from code_review_agent.config import ReviewConfig

        cfg = ReviewConfig.from_yaml(Path(config_path))
        config_overrides = cfg.model_dump()

    # CLI flags override config
    if severity or max_comments:
        config_overrides = config_overrides or {}
        if severity:
            config_overrides["severity_threshold"] = severity
        if max_comments:
            config_overrides["max_comments"] = max_comments

    result = asyncio.run(
        run_review(
            owner=owner,
            repo=repo,
            pr_number=pr_number,
            settings=settings,
            config_overrides=config_overrides,
        )
    )

    if json_output:
        output = {
            "plan": result.plan.model_dump(),
            "findings": [f.model_dump() for f in result.findings],
            "summary": result.summary,
        }
        click.echo(json.dumps(output, indent=2))
    else:
        _print_results(result)


@main.command("test-pr")
@click.argument("repo_url")
@click.option("--debug", is_flag=True)
def test_pr(repo_url: str, debug: bool) -> None:
    """Create a test PR with known issues for end-to-end testing.

    REPO_URL should be like: owner/repo
    """
    _setup_logging(debug)
    from code_review_agent.config import AgentSettings

    settings = AgentSettings(debug=debug)
    if not settings.github_token:
        console.print("[red]Error:[/] Set CRA_GITHUB_TOKEN environment variable")
        sys.exit(1)

    # Import here to avoid circular deps
    from test_harness.create_test_pr import create_test_pr

    parts = repo_url.strip("/").split("/")
    if len(parts) < 2:
        console.print("[red]Error:[/] Use format: owner/repo")
        sys.exit(1)
    owner, repo = parts[-2], parts[-1]
    asyncio.run(create_test_pr(owner, repo, settings.github_token))


def _parse_pr_url(url: str) -> tuple[str, str, int]:
    """Parse a PR URL or shorthand into (owner, repo, number)."""
    # Handle shorthand: owner/repo#123
    if "#" in url and "://" not in url:
        repo_part, num = url.rsplit("#", 1)
        parts = repo_part.strip("/").split("/")
        return parts[-2], parts[-1], int(num)

    # Handle full URL: https://github.com/owner/repo/pull/123
    url = url.rstrip("/")
    parts = url.split("/")
    try:
        pull_idx = parts.index("pull")
        return parts[pull_idx - 2], parts[pull_idx - 1], int(parts[pull_idx + 1])
    except (ValueError, IndexError):
        console.print(f"[red]Error:[/] Cannot parse PR URL: {url}")
        console.print("Use format: https://github.com/owner/repo/pull/123 or owner/repo#123")
        sys.exit(1)


def _print_results(result) -> None:
    """Pretty-print review results to the terminal."""
    console.print()
    console.print(result.summary)
    console.print()

    if not result.findings:
        return

    table = Table(title="Findings")
    table.add_column("Sev", style="bold", width=8)
    table.add_column("File", style="cyan")
    table.add_column("Line", justify="right")
    table.add_column("Title")
    table.add_column("Analyzer", style="dim")

    sev_styles = {
        "error": "red",
        "warning": "yellow",
        "suggestion": "blue",
        "info": "dim",
    }

    for f in result.findings:
        table.add_row(
            f"[{sev_styles.get(f.severity.value, '')}]{f.severity.value}[/]",
            f.file,
            str(f.line),
            f.title[:60],
            f.analyzer,
        )

    console.print(table)
    console.print()
