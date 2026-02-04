#!/bin/bash
# Wrapper script for running Bots webserver
# Usage: run-webserver.sh [options]

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BOTS_DIR="$(dirname "$SCRIPT_DIR")/bots/bots"
CONFIG_DIR="${CONFIG_DIR:-/config}"

# Default options
PORT="${PORT:-8080}"

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --port)
            PORT="$2"
            shift 2
            ;;
        --config-dir|-c)
            CONFIG_DIR="$2"
            shift 2
            ;;
        *)
            # Pass through unknown args
            EXTRA_ARGS="$EXTRA_ARGS $1"
            shift
            ;;
    esac
done

echo "Starting Bots webserver..."
echo "  Config: $CONFIG_DIR"
echo "  Port: $PORT"

# Start webserver
exec python -m bots.webserver -c"$CONFIG_DIR" $EXTRA_ARGS
