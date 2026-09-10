#!/usr/bin/env bash
#
# run-on-loki.sh — drive validate-image.sh on loki from this laptop.
#
# rsyncs this harness (incl. any uncommitted scripts) to loki, runs the battery
# there against a freshly-built image, then pulls the run artifacts back.
#
# The conductor source is built from a git ref on origin (loki git-fetches it);
# only the harness itself is rsynced. SDK repos are used in place on loki.
#
# Usage:
#   scripts/run-on-loki.sh --ref release/3.32.x [--stages all] [--port 8090]
#
set -euo pipefail

HARNESS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LOKI="${LOKI_HOST:-loki.local}"
REMOTE="${LOKI_HARNESS_DIR:-/home/nthmost/projects/git/conductor-oss/conductor-test-harness}"

echo "▶ syncing harness → $LOKI:$REMOTE"
# --delete keeps loki in sync; exclude local-only heavyweight/secret dirs.
rsync -az --delete \
  --exclude '.git' --exclude 'runs/' --exclude 'providers/secrets.env' \
  --exclude '__pycache__' --exclude '*.pyc' \
  "$HARNESS_DIR/" "$LOKI:$REMOTE/"

echo "▶ running battery on $LOKI"
# -t so we see live colored progress; pass all args straight through.
# `|| rc=$?` keeps set -e from aborting on a FAIL verdict so artifacts still sync.
rc=0
ssh -t "$LOKI" "cd '$REMOTE' && bash scripts/validate-image.sh $*" || rc=$?

echo "▶ pulling run artifacts back"
rsync -az "$LOKI:$REMOTE/runs/" "$HARNESS_DIR/runs/" 2>/dev/null || true
latest="$(ls -td "$HARNESS_DIR"/runs/*/ 2>/dev/null | head -1)"
[[ -n "$latest" ]] && { echo "▶ report: ${latest}REPORT.md"; cat "${latest}REPORT.md" 2>/dev/null || true; }
exit $rc
