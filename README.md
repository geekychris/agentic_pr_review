# AI Code Review Agent

An AI-powered code review tool for GitHub pull requests. Combines LLM intelligence with classical linting to provide thorough, actionable reviews with inline comments and code suggestions.

## Features

- **AI-Powered Review** — Uses GPT-4o (or any OpenAI-compatible model) to find logic errors, security vulnerabilities, performance issues, and style problems
- **Classical Linting** — Integrates ruff (Python), checkstyle (Java), golangci-lint (Go), clippy (Rust)
- **Smart Planning** — AI analyzes each PR to determine what to focus on and which analyzers to run
- **Inline Comments** — Posts findings directly on the relevant lines in your PR
- **Code Suggestions** — Uses GitHub's suggestion syntax so you can apply fixes with one click
- **Full File Context** — Reviews the complete file (not just the diff) to validate correctness
- **Extensible** — Custom plugins, prompt templates, and AI providers
- **Multiple Modes** — GitHub Action, local CLI, Docker, optional webhook server

## Quick Start

### 1. Install into your repo (GitHub Action)

```bash
./scripts/install.sh /path/to/your/repo --with-config
```

Or manually create `.github/workflows/ai-code-review.yml`:

```yaml
name: AI Code Review
on:
  pull_request:
    types: [opened, synchronize, reopened]
permissions:
  contents: read
  pull-requests: write
jobs:
  review:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - run: pip install code-review-agent ruff
      - env:
          CRA_GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
          CRA_OPENAI_API_KEY: ${{ secrets.OPENAI_API_KEY }}
        run: |
          code-review-agent review \
            "https://github.com/${{ github.repository }}/pull/${{ github.event.pull_request.number }}"
```

Then add `OPENAI_API_KEY` to your repo's GitHub Actions secrets.

### 2. Run locally (for debugging)

```bash
# Install
pip install -e ".[dev]"

# Set credentials
cp .env.example .env
# Edit .env with your tokens

# Review a PR (dry-run, no GitHub posting)
code-review-agent review https://github.com/owner/repo/pull/123 --dry-run --debug

# Or use the script
./scripts/debug_local.sh owner/repo#123
```

### 3. Docker

```bash
docker build -t code-review-agent .
docker run --rm \
  -e CRA_GITHUB_TOKEN \
  -e CRA_OPENAI_API_KEY \
  code-review-agent review https://github.com/owner/repo/pull/123
```

## How It Works

The agent follows a 5-stage pipeline:

```
1. Fetch   →  PR metadata, diff, full file contents via GitHub API
2. Plan    →  AI analyzes the PR and creates a review plan
3. Analyze →  Run selected analyzers (AI, linters, security, plugins)
4. Aggregate → Deduplicate, filter by severity, sort
5. Report  →  Post inline comments + summary to GitHub
```

### Planning Phase

The planner examines the PR diff and determines:
- What languages are involved
- Which focus areas matter most (correctness, security, performance, style)
- Which files need the most attention
- Which analyzers to run

This plan is logged so you can see **why** the agent focused on what it did.

### Review Focus Areas

Each focus area uses a specialized prompt template:

| Focus | What it checks |
|-------|---------------|
| **Correctness** | Logic errors, null checks, API misuse, race conditions |
| **Security** | SQL injection, XSS, hardcoded secrets, unsafe crypto |
| **Performance** | O(n²) algorithms, N+1 queries, memory leaks |
| **Style** | Naming, dead code, missing docs, inconsistency |

## Configuration

Create `.codereview.yml` in your repo root:

```yaml
ai:
  provider: openai
  model: gpt-4o
  temperature: 0.1

focus_areas:
  - correctness
  - security
  - performance
  - style

ignore_paths:
  - "*.lock"
  - "vendor/**"
  - "generated/**"

linters:
  python: { enabled: true, tool: ruff }
  java: { enabled: true, tool: checkstyle }
  go: { enabled: true, tool: golangci-lint }
  rust: { enabled: true, tool: clippy }

severity_threshold: suggestion  # minimum severity to report
max_comments: 25

custom_instructions: |
  Focus on async/await correctness in this project.
```

## Extending

### Custom Plugins

Create `.codereview/plugins/my_checker.py` in your repo:

```python
from code_review_agent.analyzers.base import BaseAnalyzer
from code_review_agent.models import Finding, Severity, Category

class MyChecker(BaseAnalyzer):
    name = "my-checker"

    async def analyze(self, pr, config, plan, file_contents):
        findings = []
        for diff_file in pr.diff_files:
            content = file_contents.get(diff_file.path, "")
            if "TODO" in content:
                findings.append(Finding(
                    file=diff_file.path,
                    line=1,
                    severity=Severity.INFO,
                    category=Category.OTHER,
                    title="TODO found",
                    description="This file contains TODO comments.",
                    analyzer=self.name,
                ))
        return findings
```

### Custom Prompt Templates

Override built-in prompts by placing `.md.j2` files in `.codereview/prompts/`:

```
.codereview/
  prompts/
    review_security.md.j2    # Overrides the built-in security prompt
    review_correctness.md.j2  # Overrides the built-in correctness prompt
```

### Adding AI Providers

Subclass `AIProvider` in `src/code_review_agent/ai/base.py` and register in `get_provider()`.

## Testing

### Run unit tests

```bash
make test
```

### End-to-end test with a real PR

Create a test PR with known issues:

```bash
# Via CLI
code-review-agent test-pr owner/repo

# Via GitHub Actions
# Go to Actions → "Create Test PR" → Run workflow
```

This creates a branch with intentionally buggy code (Python, Java, Go, Rust) and opens a PR, which triggers the self-review workflow.

## Environment Variables

| Variable | Description | Required |
|----------|-------------|----------|
| `CRA_GITHUB_TOKEN` | GitHub token with PR read/write | Yes |
| `CRA_OPENAI_API_KEY` | OpenAI API key | Yes |
| `CRA_OPENAI_ORG_ID` | OpenAI organization ID | No |
| `CRA_LOG_LEVEL` | Logging level (DEBUG, INFO, etc.) | No |
| `CRA_DRY_RUN` | Skip GitHub posting if true | No |

## CLI Reference

```
code-review-agent review <PR_URL> [OPTIONS]
  --dry-run       Don't post to GitHub
  --debug         Enable debug logging
  --config PATH   Path to local .codereview.yml
  --json-output   Output findings as JSON

code-review-agent test-pr <owner/repo>
  Create a test PR with known issues

code-review-agent --version
```

## Architecture

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for detailed design docs.

## License

MIT
