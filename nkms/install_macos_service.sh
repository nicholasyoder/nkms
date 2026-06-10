#!/usr/bin/env bash
set -e

PYTHON=$(which python3)
SCRIPT=$(realpath "$(dirname "$0")/macos_client.py")
PLIST_SRC="$(dirname "$0")/macos_launchagent.plist"
PLIST_DST="$HOME/Library/LaunchAgents/com.nkms.client.plist"

sed -e "s|__PYTHON__|$PYTHON|g" \
    -e "s|__SCRIPT__|$SCRIPT|g" \
    "$PLIST_SRC" > "$PLIST_DST"

launchctl load "$PLIST_DST"
echo "nkms client service installed and started."
echo "Logs: /tmp/nkms-client.log  /tmp/nkms-client.err"
