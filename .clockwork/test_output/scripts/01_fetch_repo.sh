#!/bin/bash
set -e
echo 'Fetching repository...'
git clone $REPO_URL .
echo 'Repository fetched successfully'
