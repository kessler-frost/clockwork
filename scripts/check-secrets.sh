#!/bin/bash

# Script to check for secrets in the codebase
# Usage: ./scripts/check-secrets.sh [--update]

set -e

echo "🔍 Clockwork Secret Detection Tool"
echo "=================================="

# Check if detect-secrets is available
if ! uv run detect-secrets --version > /dev/null 2>&1; then
    echo "❌ detect-secrets not found. Installing..."
    uv add --dev detect-secrets
    echo "✅ detect-secrets installed"
fi

# Update baseline if requested
if [[ "$1" == "--update" ]]; then
    echo "📝 Updating secrets baseline..."
    uv run detect-secrets scan --all-files \
        --exclude-files '\.venv/.*|\.clockwork/.*|\.pytest_cache/.*|\.git/.*' \
        . > .secrets.baseline
    echo "✅ Baseline updated: .secrets.baseline"
    echo ""
    echo "Review and audit the baseline:"
    echo "  uv run detect-secrets audit .secrets.baseline"
    exit 0
fi

# Scan for new secrets
echo "🔍 Scanning for secrets..."
if uv run detect-secrets scan --all-files \
    --exclude-files '\.venv/.*|\.clockwork/.*|\.pytest_cache/.*|\.git/.*' \
    --baseline .secrets.baseline .; then
    echo "✅ No new secrets detected"
else
    echo ""
    echo "❌ NEW SECRETS DETECTED!"
    echo ""
    echo "Next steps:"
    echo "  1. Review the detected secrets above"
    echo "  2. Remove any real secrets from the code"
    echo "  3. For false positives, update the baseline:"
    echo "     ./scripts/check-secrets.sh --update"
    echo "  4. Then audit the baseline:"
    echo "     uv run detect-secrets audit .secrets.baseline"
    echo ""
    exit 1
fi

echo ""
echo "📋 Current baseline status:"
if [[ -f .secrets.baseline ]]; then
    secrets_count=$(uv run detect-secrets audit .secrets.baseline --report | grep -E "Total secrets: " | grep -o '[0-9]\+' || echo "0")
    echo "  📊 Total secrets in baseline: $secrets_count"
    echo "  📁 Baseline file: .secrets.baseline"
else
    echo "  ⚠️  No baseline file found. Run with --update to create one."
fi

echo ""
echo "🛡️  Pre-commit hook status:"
if [[ -x .git/hooks/pre-commit ]]; then
    echo "  ✅ Pre-commit hook is installed and executable"
else
    echo "  ❌ Pre-commit hook not found or not executable"
    echo "     Run the setup script to install it"
fi