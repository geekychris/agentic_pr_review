#!/usr/bin/env bash
#
# Install the AI Code Review Agent into a target repository.
#
# Usage:
#   ./scripts/install.sh /path/to/target/repo [--with-config]
#
# This copies the GitHub Actions workflow file and optionally a
# starter .codereview.yml config into the target repo.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

TARGET_REPO="${1:?Usage: $0 /path/to/target/repo [--with-config]}"
WITH_CONFIG="${2:-}"

# Resolve absolute path
TARGET_REPO="$(cd "$TARGET_REPO" && pwd)"

echo "Installing AI Code Review Agent into: $TARGET_REPO"

# Create workflow directory
WORKFLOW_DIR="$TARGET_REPO/.github/workflows"
mkdir -p "$WORKFLOW_DIR"

# Write the workflow file
cat > "$WORKFLOW_DIR/ai-code-review.yml" << 'WORKFLOW'
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
  group: review-${{ github.event.pull_request.number || github.event.issue.number }}
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
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.12"

      - name: Install code-review-agent
        run: pip install code-review-agent

      - name: Install linters
        run: |
          pip install ruff  # Python
          # Add more linters as needed:
          # go install github.com/golangci/golangci-lint/cmd/golangci-lint@latest
          # cargo install clippy

      - name: Determine PR number
        id: pr
        run: |
          if [ "${{ github.event_name }}" = "pull_request" ]; then
            echo "number=${{ github.event.pull_request.number }}" >> "$GITHUB_OUTPUT"
          else
            echo "number=${{ github.event.issue.number }}" >> "$GITHUB_OUTPUT"
          fi

      - name: Run review
        env:
          CRA_GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
          CRA_OPENAI_API_KEY: ${{ secrets.OPENAI_API_KEY }}
        run: |
          PR_URL="https://github.com/${{ github.repository }}/pull/${{ steps.pr.outputs.number }}"
          code-review-agent review "$PR_URL"
WORKFLOW

echo "✓ Created $WORKFLOW_DIR/ai-code-review.yml"

# Optionally create a starter config
if [ "$WITH_CONFIG" = "--with-config" ]; then
    cat > "$TARGET_REPO/.codereview.yml" << 'CONFIG'
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
    echo "✓ Created $TARGET_REPO/.codereview.yml"
fi

echo ""
echo "Next steps:"
echo "  1. Add OPENAI_API_KEY to your repo's GitHub Actions secrets"
echo "     (Settings → Secrets and variables → Actions → New repository secret)"
echo "  2. GITHUB_TOKEN is provided automatically by GitHub Actions"
echo "  3. Commit and push the new files"
echo "  4. Open a PR to trigger the review!"
