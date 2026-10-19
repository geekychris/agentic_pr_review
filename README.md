<p align="center">
  <img src="assets/logo.png" alt="Agentic PR Review logo" width="180">
</p>

# AI Code Review Agent

An AI-powered code review tool for GitHub pull requests. Combines LLM analysis with classical linting to provide thorough, actionable reviews — posted as inline comments with one-click code suggestions.

## Features

- **AI-Powered Review** — GPT-4o (or any OpenAI-compatible model) finds logic errors, security vulnerabilities, performance issues, and style problems
- **Classical Linting** — Integrates ruff (Python), checkstyle (Java), golangci-lint (Go), clippy (Rust)
- **Smart Planning** — AI analyzes each PR to determine focus areas and which analyzers to run
- **Severity-Tiered Output** — Critical issues prominently displayed; warnings visible; suggestions and info collapsed in the summary
- **Inline Threshold** — Only high-severity findings get inline comments; lower-severity go to the summary to reduce noise
- **Stratified Limits** — Per-file and global comment caps ensure severity diversity (not just the first N findings)
- **Code Suggestions** — Uses GitHub's suggestion syntax for one-click apply
- **Full File Context** — Reviews the complete file (not just the diff) to validate correctness
- **Extensible** — Custom plugins, prompt templates, and AI providers
- **Multiple Modes** — GitHub Action, local CLI, Docker

---

## Quick Start

### 1. Install into any repo (recommended)

The install script sets up a GitHub Actions workflow that references this repo's `action.yml` — **no code is copied** into the target repo.

```bash
# Install into a remote repo (via GitHub API) and set the OpenAI secret
./scripts/install.sh owner/repo --set-secret --with-config

# Install into a local clone
./scripts/install.sh /path/to/your/repo --with-config

# Pin to a specific version/branch
./scripts/install.sh owner/repo --branch v1.0 --set-secret
```

**Install script options:**

- First argument: `owner/repo` (remote) or `/path/to/repo` (local)
- `--with-config` — Creates a starter `.codereview.yml` in the target repo
- `--set-secret` — Prompts for your OpenAI API key and sets it as a GitHub Actions secret via `gh secret set`
- `--branch NAME` — Branch or tag of the action to reference (default: `main`)

The script auto-detects the action source from this repo's git remote, so it works from any clone of this project.

### 2. Manual workflow setup

If you prefer to set up the workflow by hand, create `.github/workflows/ai-code-review.yml` in your target repo:

```yaml
name: AI Code Review
on:
  pull_request:
    types: [opened, synchronize, reopened]
  issue_comment:
    types: [created]
permissions:
  contents: read
  pull-requests: write
jobs:
  review:
    runs-on: ubuntu-latest
    if: |
      github.event_name == 'pull_request' ||
      (github.event_name == 'issue_comment' &&
       github.event.issue.pull_request &&
       contains(github.event.comment.body, '/review'))
    steps:
      - uses: geekychris/agentic_pr_review@main
        with:
          github_token: ${{ secrets.GITHUB_TOKEN }}
          openai_api_key: ${{ secrets.OPENAI_API_KEY }}
```

Then set up secrets (see [Setting Up Secrets](#setting-up-secrets) below).

### 3. Run locally (for debugging)

```bash
# Install in dev mode
pip install -e ".[dev]"

# Set credentials
cp .env.example .env
# Edit .env with your tokens

# Review a PR (dry-run — prints findings, doesn't post to GitHub)
code-review-agent review https://github.com/owner/repo/pull/123 --dry-run --debug

# Review and post to GitHub
code-review-agent review https://github.com/owner/repo/pull/123
```

### 4. Docker

```bash
docker build -t code-review-agent .
docker run --rm \
  -e CRA_GITHUB_TOKEN \
  -e CRA_OPENAI_API_KEY \
  code-review-agent review https://github.com/owner/repo/pull/123
```

### 5. Trigger on demand

Comment `/review` on any open PR to re-trigger the review (requires the `issue_comment` event in the workflow).

---

## How It Works

The agent follows a 5-stage pipeline:

```
1. Fetch     →  PR metadata, diff, full file contents via GitHub API
2. Plan      →  AI analyzes the PR and creates a review plan
3. Analyze   →  Run selected analyzers (AI, linters, security, plugins)
4. Aggregate →  Deduplicate, filter by severity, apply stratified limits
5. Report    →  Post inline comments + severity-tiered summary to GitHub
```

### Planning Phase

The planner examines the PR diff and determines:
- What languages are involved
- Which focus areas matter most (correctness, security, performance, style)
- Which files need the most attention
- Which analyzers to run

The plan is logged for transparency so you can see **why** the agent focused on what it did.

### Review Focus Areas

Each focus area uses a specialized Jinja2 prompt template:

- **Correctness** — Logic errors, null checks, API misuse, race conditions, concurrency bugs
- **Security** — SQL injection, XSS, command injection, hardcoded secrets, unsafe crypto
- **Performance** — O(n²) algorithms, N+1 queries, memory/resource leaks
- **Style** — Naming, dead code, missing docs, inconsistency, verbose patterns

### Severity Levels

Findings are classified into four levels, each with distinct handling:

- 🚨 **error** — Will cause crashes, data loss, or security exploits. Always shown prominently.
- ⚠️ **warning** — Likely to cause bugs under certain conditions. Shown in summary.
- 💡 **suggestion** — Code works but could be improved. Collapsed in summary.
- ℹ️ **info** — Observations (TODOs, minor notes). Collapsed in summary.

The **inline threshold** (`inline_threshold` config) controls which findings get inline PR comments vs. summary-only placement. Default: `warning` (only warnings and errors get inline comments).

---

## Configuration

Create `.codereview.yml` in your repo root (or use `--with-config` in the install script):

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
  - "node_modules/**"

linters:
  python: { enabled: true, tool: ruff }
  java: { enabled: true, tool: checkstyle }
  go: { enabled: true, tool: golangci-lint }
  rust: { enabled: true, tool: clippy }

# Severity controls
severity_threshold: suggestion   # Minimum severity to include anywhere
inline_threshold: warning        # Minimum severity for inline PR comments
max_comments: 25                 # Global cap on inline comments
max_comments_per_file: 10        # Per-file cap on inline comments

custom_instructions: |
  Focus on async/await correctness in this project.
```

### Configuration Reference

- **`ai.provider`** — AI backend (`openai`). Default: `openai`
- **`ai.model`** — Model name. Default: `gpt-4o`
- **`ai.temperature`** — LLM temperature. Default: `0.1`
- **`focus_areas`** — List of review focus areas. Default: `[correctness, security, performance, style]`
- **`ignore_paths`** — Glob patterns for files to skip
- **`linters`** — Per-language linter config (each has `enabled` and `tool`)
- **`severity_threshold`** — Minimum severity to report anywhere. Default: `suggestion`
- **`inline_threshold`** — Minimum severity for inline comments (lower go to summary only). Default: `warning`
- **`max_comments`** — Global inline comment cap. Default: `25`
- **`max_comments_per_file`** — Per-file inline comment cap. Default: `10`
- **`custom_instructions`** — Extra instructions appended to every AI prompt

---

## GitHub Action Inputs

When using the reusable action directly:

```yaml
- uses: geekychris/agentic_pr_review@main
  with:
    github_token: ${{ secrets.GITHUB_TOKEN }}   # Required (auto-provided)
    openai_api_key: ${{ secrets.OPENAI_API_KEY }} # Required
    openai_model: gpt-4o          # Optional, default: gpt-4o
    debug: false                  # Optional, default: false
    max_comments: 25              # Optional, default: 25
    severity_threshold: suggestion # Optional, default: suggestion
```

---

## CLI Reference

```
code-review-agent review <PR_URL> [OPTIONS]

  PR_URL: https://github.com/owner/repo/pull/123 or owner/repo#123

  --dry-run                  Print findings without posting to GitHub
  --debug                    Enable debug logging
  --config PATH              Path to a local .codereview.yml
  --json-output              Output findings as JSON
  --severity LEVEL           Override severity_threshold (error|warning|suggestion|info)
  --max-comments N           Override max_comments

code-review-agent test-pr <owner/repo>
  Create a test PR with intentionally buggy code for end-to-end testing.
  --debug                    Enable debug logging

code-review-agent --version
```

---

## Setting Up Secrets

The agent needs two credentials to run in GitHub Actions:

### 1. `OPENAI_API_KEY` (you must set this)

Your OpenAI API key. Set it as a GitHub Actions secret on the target repo.

**Option A: Via the install script (easiest)**

```bash
./scripts/install.sh owner/repo --set-secret --with-config
# The script will prompt you to paste your key (input is hidden)
```

**Option B: Via `gh` CLI**

```bash
# Interactive (prompts for the key)
gh secret set OPENAI_API_KEY --repo owner/repo

# Or pipe from a file
gh secret set OPENAI_API_KEY --repo owner/repo < ~/openai-key.txt

# Or from an existing .env file
grep '^CRA_OPENAI_API_KEY=' .env | cut -d= -f2- | gh secret set OPENAI_API_KEY --repo owner/repo
```

**Option C: Via GitHub web UI**

1. Go to your repo on GitHub
2. Navigate to **Settings** → **Secrets and variables** → **Actions**
3. Click **New repository secret**
4. Name: `OPENAI_API_KEY`
5. Value: your OpenAI API key (starts with `sk-`)
6. Click **Add secret**

### 2. `GITHUB_TOKEN` (automatic — no setup needed)

GitHub automatically provides a `GITHUB_TOKEN` to every Actions run. The workflow uses it to read PR diffs and post review comments.

**Default permissions** are sufficient if your repo has:
- **Settings** → **Actions** → **General** → **Workflow permissions** set to **Read and write permissions**

If your org restricts the default token, ensure it has these scopes:
- `contents: read` — to read file contents
- `pull-requests: write` — to post reviews and comments

### Verifying secrets are set

```bash
# List all secrets on the repo (values are hidden)
gh secret list --repo owner/repo
```

You should see `OPENAI_API_KEY` in the list. `GITHUB_TOKEN` won't appear — it's injected automatically.

---

## Environment Variables

For local CLI usage, set these in a `.env` file or export them:

- **`CRA_GITHUB_TOKEN`** — GitHub personal access token with `repo` scope. *Required for local use.*
- **`CRA_OPENAI_API_KEY`** — OpenAI API key. *Required.*
- **`CRA_OPENAI_ORG_ID`** — OpenAI organization ID. *Optional.*
- **`CRA_LOG_LEVEL`** — Logging level (`DEBUG`, `INFO`, `WARNING`, `ERROR`). Default: `INFO`
- **`CRA_DRY_RUN`** — Set `true` to skip GitHub posting. Default: `false`

```bash
# Quick setup for local use
cp .env.example .env
# Edit .env with your values
```

Credentials are loaded automatically via pydantic-settings from `.env` or environment variables.

---

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
    review_security.md.j2      # Overrides the built-in security prompt
    review_correctness.md.j2   # Overrides the built-in correctness prompt
    review_performance.md.j2
    review_style.md.j2
```

### Adding AI Providers

Subclass `AIProvider` in `src/code_review_agent/ai/base.py` and register in `get_provider()`.

---

## Testing

```bash
# Run unit tests
make test

# Run with coverage
make test-cov

# Lint
make lint

# Auto-format
make format
```

### End-to-end test with a real PR

The `test-pr` command creates a branch with intentionally buggy code (Python, Java, Go, Rust) containing issues at every severity level — deadlocks, SQL injection, resource leaks, concurrency bugs, style issues, and more.

```bash
# Create a test PR
code-review-agent test-pr owner/repo

# Then review it
code-review-agent review https://github.com/owner/repo/pull/N
```

---

## Architecture

- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) — High-level design decisions
- [docs/IMPLEMENTATION.md](docs/IMPLEMENTATION.md) — Detailed implementation guide with Mermaid diagrams, data models, and improvement roadmap

---

## Development

```bash
# Clone and install in dev mode
git clone git@github.com:geekychris/agentic_pr_review.git
cd agentic_pr_review
make dev

# Run tests
make test

# Local dry-run review
make review-dry PR_URL=https://github.com/owner/repo/pull/123
```

Requires Python ≥ 3.11.

## License

MIT
