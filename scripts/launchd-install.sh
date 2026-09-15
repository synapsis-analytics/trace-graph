#!/usr/bin/env bash
# Write + load the launchd agent for one TRACE environment.
#   scripts/launchd-install.sh dev|test|prod
set -euo pipefail
ENV_NAME="${1:-}"
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENVS_ROOT="${TRACE_ENVS_ROOT:-$HOME/workspace/trace-graph-envs}"
case "$ENV_NAME" in
  dev)  PORT=8413; WORKTREE="$HOME/workspace/trace-graph" ;;
  test) PORT=8414; WORKTREE="$ENVS_ROOT/test" ;;
  prod) PORT=8415; WORKTREE="$ENVS_ROOT/prod" ;;
  *) echo "usage: scripts/launchd-install.sh dev|test|prod" >&2; exit 2 ;;
esac
[ -d "$WORKTREE" ] || { echo "no worktree at $WORKTREE — run scripts/deploy.sh $ENV_NAME first" >&2; exit 1; }
LABEL="com.synapsis.trace-graph-${ENV_NAME}"
PLIST="$HOME/Library/LaunchAgents/${LABEL}.plist"
mkdir -p "$HOME/Library/LaunchAgents" "$WORKTREE/data"
cat > "$PLIST" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>Label</key><string>${LABEL}</string>
  <key>ProgramArguments</key><array><string>/bin/bash</string><string>${WORKTREE}/scripts/run.sh</string></array>
  <key>WorkingDirectory</key><string>${WORKTREE}</string>
  <key>EnvironmentVariables</key><dict>
    <key>PORT</key><string>${PORT}</string>
    <key>PATH</key><string>/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin</string>
  </dict>
  <key>RunAtLoad</key><true/>
  <key>KeepAlive</key><true/>
  <key>ThrottleInterval</key><integer>5</integer>
  <key>StandardOutPath</key><string>${WORKTREE}/data/server.log</string>
  <key>StandardErrorPath</key><string>${WORKTREE}/data/server.log</string>
</dict></plist>
EOF
launchctl bootout "gui/$(id -u)/${LABEL}" 2>/dev/null || true
launchctl bootstrap "gui/$(id -u)" "$PLIST"
echo "installed ${LABEL} -> ${WORKTREE} :${PORT} (logs: ${WORKTREE}/data/server.log)"
