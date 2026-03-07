"""Abstract base class for all analyzers."""

from __future__ import annotations

from abc import ABC, abstractmethod

from code_review_agent.config import ReviewConfig
from code_review_agent.models import Finding, PRInfo, ReviewPlan


class BaseAnalyzer(ABC):
    """Interface for review analyzers.

    Each analyzer receives the PR info, config, and review plan, and
    returns a list of findings.  Analyzers run in parallel during the
    Analyze phase of the pipeline.

    To create a custom analyzer:
    1. Subclass ``BaseAnalyzer``
    2. Implement ``analyze()``
    3. Register via the plugin loader or add to the pipeline directly
    """

    name: str = "base"

    @abstractmethod
    async def analyze(
        self,
        pr: PRInfo,
        config: ReviewConfig,
        plan: ReviewPlan,
        file_contents: dict[str, str],
    ) -> list[Finding]:
        """Run the analysis and return findings.

        Parameters
        ----------
        pr : PRInfo
            Pull request metadata including parsed diffs.
        config : ReviewConfig
            Repo-level configuration.
        plan : ReviewPlan
            The review plan from the planning phase.
        file_contents : dict[str, str]
            Mapping of file path → full file content at the HEAD ref.
        """
