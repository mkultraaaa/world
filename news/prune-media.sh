#!/bin/bash
# Delete news media older than RETENTION_DAYS.
# Runs on Pro before the daily build so old files get git-rm'd in the same commit.
set -euo pipefail

RETENTION_DAYS="${RETENTION_DAYS:-14}"

NEWS_MEDIA="$HOME/projects/world/news/media"
TG_MEDIA="$HOME/.openclaw/workspace/data/tg-gateway/out/media"

prune() {
    local dir="$1"
    [ -d "$dir" ] || return 0
    local n
    n=$(find "$dir" -type f -mtime +"$RETENTION_DAYS" -print -delete 2>/dev/null | wc -l | tr -d ' ')
    echo "pruned $n files from $dir (older than ${RETENTION_DAYS}d)"
}

prune "$NEWS_MEDIA"
prune "$TG_MEDIA"
