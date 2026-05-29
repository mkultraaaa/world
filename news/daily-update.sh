#!/bin/bash
# Daily news digest: build HTML from feed.jsonl and push to Vercel
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
WORLD_DIR="$(dirname "$SCRIPT_DIR")"
LOG="$SCRIPT_DIR/daily-update.log"

exec >> "$LOG" 2>&1
echo "=== $(date '+%Y-%m-%d %H:%M:%S') START ==="

# Drop media older than retention window (also prunes tg-gateway/out/media)
bash "$SCRIPT_DIR/prune-media.sh"

# Build HTML from feed.jsonl
cd "$SCRIPT_DIR"
/usr/bin/python3 build.py

# Check if anything changed (-A so deletions are picked up too)
cd "$WORLD_DIR"
git add -A news/index.html news/media/
if git diff --cached --quiet -- news/index.html news/media/; then
    echo "No changes, skipping push"
    echo "=== $(date '+%Y-%m-%d %H:%M:%S') DONE (no changes) ==="
    exit 0
fi

# Commit and push
git commit -m "Daily news update $(date '+%Y-%m-%d')"
git push origin main

echo "=== $(date '+%Y-%m-%d %H:%M:%S') DONE (pushed) ==="
