#!/bin/bash
set -e
echo 'Fetching repository...'
REPO_URL="$1"
REPO_REF="$2"
git clone --branch "$REPO_REF" "$REPO_URL" .
echo 'Repository fetched successfully'
