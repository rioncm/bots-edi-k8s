#!/bin/bash
# Wrapper script for running Bots job queue server
# Usage: run-jobqueue.sh [options]

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONFIG_DIR="${CONFIG_DIR:-/config}"

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
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

echo "Starting Bots job queue server..."
echo "  Config: $CONFIG_DIR"
echo "  Args: $EXTRA_ARGS"

# Start jobqueueserver
exec python -m bots.jobqueueserver -c"$CONFIG_DIR" $EXTRA_ARGS
