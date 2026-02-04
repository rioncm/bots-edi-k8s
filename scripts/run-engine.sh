#!/bin/bash
# Wrapper script for running Bots engine
# Usage: run-engine.sh [options]

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

echo "Starting Bots engine..."
echo "  Config: $CONFIG_DIR"
echo "  Args: $EXTRA_ARGS"

# Start engine
exec python -m bots.engine -c"$CONFIG_DIR" $EXTRA_ARGS
