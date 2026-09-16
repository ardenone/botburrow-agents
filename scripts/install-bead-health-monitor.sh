#!/usr/bin/env bash
# Install the botburrow bead-health-monitor user units on this host and
# enable the 5-minute timer.
#
# Idempotent: re-running refreshes the unit files and re-enables the timer.
# The units live in the repo (systemd/user/) so deployment is reproducible;
# this script only copies them into ~/.config/systemd/user/ and starts the
# timer. Logs land in the persistent user journal:
#   journalctl --user -u botburrow-bead-health-monitor.service
#
# Usage:
#   ./scripts/install-bead-health-monitor.sh

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
UNIT_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/systemd/user"
SERVICE=botburrow-bead-health-monitor.service
TIMER=botburrow-bead-health-monitor.timer

mkdir -p "$UNIT_DIR"
install -m 644 "$REPO_ROOT/systemd/user/$SERVICE" "$UNIT_DIR/$SERVICE"
install -m 644 "$REPO_ROOT/systemd/user/$TIMER" "$UNIT_DIR/$TIMER"

systemctl --user daemon-reload
systemctl --user enable --now "$TIMER" >/dev/null

echo "Installed and enabled. Timer status:"
systemctl --user list-timers --no-pager "$TIMER"
echo
echo "Recent runs:   journalctl --user -u $SERVICE -n 50"
echo "Run one now:   systemctl --user start $SERVICE"
