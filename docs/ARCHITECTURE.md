# Architecture

## Overview

The AI Code Review Agent is a Python application that reviews GitHub pull requests using a combination of AI (LLM) analysis and classical linting tools. It runs as a GitHub Action (no server needed), a local CLI, or a Docker container.

## Pipeline

Every review follows a 5-stage pipeline:

```
Fetch → Plan → Analyze → Aggregate → Report
```

### Stage 1: Fetch
- Retrieves PR metadata (title, description, author, SHAs) via GitHub REST API
- Downloads the unified diff and parses it into structured `DiffFile`/`DiffHunk` objects
- Fetches full file contents at the HEAD ref for context
- Loads `.codereview.yml` config from the repo if present

### Stage 2: Plan
- Sends PR metadata + file list to the AI with the `planning.md.j2` prompt
- AI produces a `ReviewPlan`: which languages, focus areas, priority files, analyzers
- The plan is logged for transparency — you can see WHY the agent chose its approach
- Falls back to a sensible default plan if the AI fails

### Stage 3: Analyze
- Instantiates analyzers based on the plan (AI, Linter, Security, custom plugins)
- Runs all analyzers concurrently via `asyncio.gather`
- **AI Analyzer**: For each file × focus area, sends diff + full file to the AI with a focus-specific prompt; parses JSON response into `Finding` objects
- **Linter Analyzer**: Runs language-appropriate linters (ruff, checkstyle, etc.), parses output, filters to changed lines only
- **Security Analyzer**: Dedicated security pass (skips if AI analyzer already covers security)
- **Plugin Analyzer**: Loads custom `.codereview/plugins/*.py` modules

### Stage 4: Aggregate
- Deduplicates findings (same file + line + category)
- Filters by severity threshold (configured in `.codereview.yml`)
- Sorts by severity (errors first), then file/line
- Caps at `max_comments` to avoid flooding the PR

### Stage 5: Report
- Uses the GitHub Pull Request Reviews API to post a single review
- Each finding becomes an inline comment on the relevant line
- Code suggestions use GitHub's ` ```suggestion ``` ` syntax for one-click apply
- Summary includes finding counts by severity and category
- Falls back to a regular PR comment if the review API fails

## Key Design Decisions

### Full file context
The AI receives the complete file, not just the diff. This allows it to validate that changes integrate correctly with surrounding code — catching issues like broken function contracts or incorrect variable references that wouldn't be visible in the diff alone.

### Linter filtering
Linters run on the full file, but findings are filtered to only lines that appear in the diff. This prevents the agent from flagging pre-existing issues that aren't part of the current PR.

### Planning phase
Instead of applying all checks uniformly, the AI first analyzes the PR to determine what matters. A documentation-only PR gets style focus; a security-critical change gets security focus. This reduces noise and cost.

### Pluggable everything
- **AI Providers**: Abstract `AIProvider` base class with OpenAI implementation; trivial to add Anthropic, local models, etc.
- **Analyzers**: Abstract `BaseAnalyzer`; add new analysis types without touching the pipeline
- **Linters**: Abstract `BaseLinter`; add language support by implementing one class
- **Prompts**: Jinja2 templates that repos can override

## File Structure

```
src/code_review_agent/
├── cli.py            # Click CLI entry point
├── config.py         # Pydantic configuration models
├── models.py         # Core data models (Finding, ReviewPlan, etc.)
├── github_client.py  # Async GitHub REST API client
├── diff_parser.py    # Unified diff → structured data
├── pipeline.py       # 5-stage pipeline orchestration
├── planner.py        # AI planning phase
├── reporter.py       # GitHub review posting
├── ai/
│   ├── base.py       # Abstract AI provider
│   ├── openai_provider.py
│   └── prompts.py    # Jinja2 template renderer
├── analyzers/
│   ├── base.py       # Abstract analyzer
│   ├── ai_analyzer.py
│   ├── linter_analyzer.py
│   └── security_analyzer.py
├── linters/
│   ├── base.py       # Abstract linter + factory
│   ├── python_linter.py   # ruff
│   ├── java_linter.py     # checkstyle
│   ├── go_linter.py       # golangci-lint
│   └── rust_linter.py     # clippy
└── plugins/
    └── loader.py     # Custom plugin discovery
```
