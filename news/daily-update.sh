#!/bin/bash
# Daily news digest: build HTML from feed.jsonl and push to Vercel
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
WORLD_DIR="$(dirname "$SCRIPT_DIR")"
LOG="$SCRIPT_DIR/daily-update.log"

exec >> "$LOG" 2>&1
echo "=== $(date '+%Y-%m-%d %H:%M:%S') START ==="

# Build HTML from feed.jsonl
cd "$SCRIPT_DIR"
/usr/bin/python3 build.py

# Check if anything changed
cd "$WORLD_DIR"
if git diff --quiet news/index.html news/media/ 2>/dev/null; then
    echo "No changes, skipping push"
    echo "=== $(date '+%Y-%m-%d %H:%M:%S') DONE (no changes) ==="
    exit 0
fi

# Commit and push
git add news/index.html news/media/
git commit -m "Daily news update $(date '+%Y-%m-%d')"
git push origin main

echo "=== $(date '+%Y-%m-%d %H:%M:%S') DONE (pushed) ==="
