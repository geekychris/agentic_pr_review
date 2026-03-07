#!/usr/bin/env bash
#
# Install the AI Code Review Agent into a target repository.
#
# Usage:
#   ./scripts/install.sh <owner/repo or /path/to/repo> [OPTIONS]
#
# Options:
#   --with-config     Also create a starter .codereview.yml
#   --set-secret      Prompt for OPENAI_API_KEY and set it as a GitHub secret
#   --branch NAME     Branch/tag of the action to reference (default: main)
#
# Examples:
#   ./scripts/install.sh geekychris/test_repo --set-secret --with-config
#   ./scripts/install.sh /path/to/local/repo --with-config
#   ./scripts/install.sh geekychris/myapp --branch v1.0
#
# The workflow references this repo's action.yml — no code is copied.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

# ── Resolve action source repo (owner/repo) from this project's git remote ──
ACTION_REPO="$(
  git -C "$PROJECT_DIR" remote get-url origin 2>/dev/null \
    | sed -E 's#(git@github\.com:|https://github\.com/)##; s#\.git$##'
)"
if [ -z "$ACTION_REPO" ]; then
  echo "Error: cannot determine action source repo from git remote" >&2
  exit 1
fi

# ── Parse arguments ──
TARGET="${1:?Usage: $0 <owner/repo or /path/to/repo> [--with-config] [--set-secret] [--branch NAME]}"
shift

WITH_CONFIG=false
SET_SECRET=false
ACTION_BRANCH="main"

while [ $# -gt 0 ]; do
  case "$1" in
    --with-config) WITH_CONFIG=true ;;
    --set-secret)  SET_SECRET=true ;;
    --branch)      shift; ACTION_BRANCH="${1:?--branch requires a value}" ;;
    *) echo "Unknown option: $1" >&2; exit 1 ;;
  esac
  shift
done

# ── Determine if TARGET is a local path or a GitHub owner/repo ──
if [ -d "$TARGET" ]; then
  # Local path — work directly on the filesystem
  TARGET_PATH="$(cd "$TARGET" && pwd)"
  # Derive owner/repo from the local repo's remote for gh commands
  TARGET_REPO="$(
    git -C "$TARGET_PATH" remote get-url origin 2>/dev/null \
      | sed -E 's#(git@github\.com:|https://github\.com/)##; s#\.git$##'
  )"
  MODE="local"
  echo "Installing AI Code Review Agent into local repo: $TARGET_PATH"
  echo "  GitHub repo: $TARGET_REPO"
else
  # Assume owner/repo — use GitHub API
  TARGET_REPO="$TARGET"
  MODE="remote"
  echo "Installing AI Code Review Agent into: $TARGET_REPO"
fi

echo "  Action source: $ACTION_REPO@$ACTION_BRANCH"
echo ""

# ── Build the workflow content ──
# Uses the reusable action from this repo — no code is copied.
read -r -d '' WORKFLOW_CONTENT << WORKFLOW || true
name: AI Code Review

on:
  pull_request:
    types: [opened, synchronize, reopened]
  issue_comment:
    types: [created]

permissions:
  contents: read
  pull-requests: write
  issues: write

concurrency:
  group: review-\${{ github.event.pull_request.number || github.event.issue.number }}
  cancel-in-progress: true

jobs:
  review:
    runs-on: ubuntu-latest
    if: |
      github.event_name == 'pull_request' ||
      (github.event_name == 'issue_comment' &&
       github.event.issue.pull_request &&
       contains(github.event.comment.body, '/review'))
    steps:
      - uses: ${ACTION_REPO}@${ACTION_BRANCH}
        with:
          github_token: \${{ secrets.GITHUB_TOKEN }}
          openai_api_key: \${{ secrets.OPENAI_API_KEY }}
WORKFLOW

# ── Build optional config content ──
read -r -d '' CONFIG_CONTENT << 'CONFIG' || true
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
  python:
    enabled: true
    tool: ruff
  java:
    enabled: true
    tool: checkstyle
  go:
    enabled: true
    tool: golangci-lint
  rust:
    enabled: true
    tool: clippy

severity_threshold: suggestion
max_comments: 25
CONFIG

# ── Install files ──
if [ "$MODE" = "local" ]; then
  # Write directly to the filesystem
  WORKFLOW_DIR="$TARGET_PATH/.github/workflows"
  mkdir -p "$WORKFLOW_DIR"
  echo "$WORKFLOW_CONTENT" > "$WORKFLOW_DIR/ai-code-review.yml"
  echo "✓ Created $WORKFLOW_DIR/ai-code-review.yml"

  if [ "$WITH_CONFIG" = true ]; then
    echo "$CONFIG_CONTENT" > "$TARGET_PATH/.codereview.yml"
    echo "✓ Created $TARGET_PATH/.codereview.yml"
  fi
else
  # Use GitHub API to commit files to the remote repo
  if ! command -v gh &>/dev/null; then
    echo "Error: 'gh' CLI is required for remote installs. Install: brew install gh" >&2
    exit 1
  fi

  # Get default branch
  DEFAULT_BRANCH="$(gh api "repos/$TARGET_REPO" --jq '.default_branch')"

  # Create workflow file via GitHub API
  echo "$WORKFLOW_CONTENT" | gh api \
    "repos/$TARGET_REPO/contents/.github/workflows/ai-code-review.yml" \
    --method PUT \
    --field message="ci: add AI code review agent workflow" \
    --field branch="$DEFAULT_BRANCH" \
    --field content=@- \
    --silent 2>/dev/null \
    && echo "✓ Created .github/workflows/ai-code-review.yml" \
    || {
      # File may already exist — try update
      SHA="$(gh api "repos/$TARGET_REPO/contents/.github/workflows/ai-code-review.yml" \
        --jq '.sha' 2>/dev/null || true)"
      if [ -n "$SHA" ]; then
        echo "$WORKFLOW_CONTENT" | base64 | gh api \
          "repos/$TARGET_REPO/contents/.github/workflows/ai-code-review.yml" \
          --method PUT \
          --field message="ci: update AI code review agent workflow" \
          --field branch="$DEFAULT_BRANCH" \
          --field sha="$SHA" \
          --field content=@- \
          --silent
        echo "✓ Updated .github/workflows/ai-code-review.yml"
      else
        echo "✗ Failed to create workflow file" >&2
        exit 1
      fi
    }

  if [ "$WITH_CONFIG" = true ]; then
    echo "$CONFIG_CONTENT" | gh api \
      "repos/$TARGET_REPO/contents/.codereview.yml" \
      --method PUT \
      --field message="ci: add code review agent config" \
      --field branch="$DEFAULT_BRANCH" \
      --field content=@- \
      --silent 2>/dev/null \
      && echo "✓ Created .codereview.yml" \
      || echo "⚠ .codereview.yml already exists (skipped)"
  fi
fi

# ── Set OPENAI_API_KEY secret ──
if [ "$SET_SECRET" = true ]; then
  if ! command -v gh &>/dev/null; then
    echo "Error: 'gh' CLI is required to set secrets. Install: brew install gh" >&2
    exit 1
  fi

  echo ""
  echo "Setting OPENAI_API_KEY secret on $TARGET_REPO..."
  echo "Paste your OpenAI API key (input is hidden):"
  read -rs OPENAI_KEY
  echo ""

  if [ -z "$OPENAI_KEY" ]; then
    echo "⚠ No key provided — skipping secret setup"
  else
    echo "$OPENAI_KEY" | gh secret set OPENAI_API_KEY --repo "$TARGET_REPO"
    echo "✓ OPENAI_API_KEY secret set on $TARGET_REPO"
  fi
fi

echo ""
echo "Done! The workflow references $ACTION_REPO@$ACTION_BRANCH"
echo "(no code was copied — the target repo uses the action from the source repo)"
echo ""
echo "Remaining steps:"
if [ "$SET_SECRET" != true ]; then
  echo "  1. Set the OpenAI secret: gh secret set OPENAI_API_KEY --repo $TARGET_REPO"
  echo "  2. GITHUB_TOKEN is provided automatically by GitHub Actions"
else
  echo "  1. GITHUB_TOKEN is provided automatically by GitHub Actions"
fi
if [ "$MODE" = "local" ]; then
  echo "  • Commit and push the new files"
fi
echo "  • Open a PR to trigger the review!"
