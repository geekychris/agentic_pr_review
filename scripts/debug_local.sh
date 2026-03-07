#!/usr/bin/env bash
#
# Run a local dry-run review for debugging.
#
# Usage:
#   ./scripts/debug_local.sh https://github.com/owner/repo/pull/123
#   ./scripts/debug_local.sh owner/repo#123
#
# Requires .env file with CRA_GITHUB_TOKEN and CRA_OPENAI_API_KEY set.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

PR_URL="${1:?Usage: $0 <pr_url>}"

# Load .env if it exists
if [ -f "$PROJECT_DIR/.env" ]; then
    echo "Loading .env..."
    set -a
    source "$PROJECT_DIR/.env"
    set +a
fi

# Check required vars
if [ -z "${CRA_GITHUB_TOKEN:-}" ]; then
    echo "Error: CRA_GITHUB_TOKEN not set. Create a .env file or export it."
    exit 1
fi

if [ -z "${CRA_OPENAI_API_KEY:-}" ]; then
    echo "Error: CRA_OPENAI_API_KEY not set. Create a .env file or export it."
    exit 1
fi

echo "Running dry-run review for: $PR_URL"
echo "---"

code-review-agent review "$PR_URL" --dry-run --debug
