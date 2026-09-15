#!/usr/bin/env bash
# Stop + remove the launchd agent for one TRACE environment (the data is left untouched).
set -euo pipefail
ENV_NAME="${1:-}"
case "$ENV_NAME" in dev|test|prod) ;; *) echo "usage: scripts/launchd-uninstall.sh dev|test|prod" >&2; exit 2 ;; esac
LABEL="com.synapsis.trace-graph-${ENV_NAME}"
launchctl bootout "gui/$(id -u)/${LABEL}" 2>/dev/null || true
rm -f "$HOME/Library/LaunchAgents/${LABEL}.plist"
echo "removed ${LABEL}"
