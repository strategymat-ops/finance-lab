#!/bin/bash
# ============================================================================
# Finance Lab — Real-Time Terminal Mirroring (Google Cloud Shell <-> Local Terminal)
# ============================================================================
# Uses tmate / tmux to provide 100% synchronous dual-screen terminal mirroring.
# Whatever is typed in Cloud Shell appears in your local terminal and vice versa!
# ============================================================================

set -e

echo "=== Finance Lab Terminal Mirror Setup ==="

if ! command -v tmate &> /dev/null; then
    echo "Installing tmate for zero-latency terminal mirroring..."
    sudo apt-get update -qq && sudo apt-get install -y -qq tmate
fi

# Start shared terminal session
echo "Starting mirrored session..."
echo "To attach from your local machine, run the SSH command shown below:"
echo "------------------------------------------------------------------"
tmate -F
