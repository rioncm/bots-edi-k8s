#!/bin/bash
# Test script for Phase 2: Health Check Endpoints
#
# Tests both web-based endpoints (via Django server) and CLI health checks
#
# Usage:
#   ./test-healthchecks.sh [--cli-only]
#
# Options:
#   --cli-only    Only test CLI health checks, skip web server tests

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
BOTS_DIR="$PROJECT_ROOT/bots"
CONFIG_DIR="$PROJECT_ROOT/bots_config"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo "=================================================="
echo "Phase 2: Health Check Testing"
echo "=================================================="
echo ""

# Check if CLI-only mode
CLI_ONLY=false
if [[ "$1" == "--cli-only" ]]; then
    CLI_ONLY=true
    echo "Running in CLI-only mode"
    echo ""
fi

# Test 1: CLI Health Checks
echo "Test 1: CLI Health Checks"
echo "--------------------------"

echo "Testing liveness check..."
if python "$SCRIPT_DIR/healthcheck.py" --check live --config-dir "$CONFIG_DIR"; then
    echo -e "${GREEN}✓ Liveness check passed${NC}"
else
    echo -e "${RED}✗ Liveness check failed${NC}"
    exit 1
fi
echo ""

echo "Testing readiness check..."
if python "$SCRIPT_DIR/healthcheck.py" --check ready --config-dir "$CONFIG_DIR"; then
    echo -e "${GREEN}✓ Readiness check passed${NC}"
else
    echo -e "${YELLOW}⚠ Readiness check failed (may be expected if DB not configured)${NC}"
fi
echo ""

echo "Testing startup check..."
if python "$SCRIPT_DIR/healthcheck.py" --check startup --config-dir "$CONFIG_DIR"; then
    echo -e "${GREEN}✓ Startup check passed${NC}"
else
    echo -e "${YELLOW}⚠ Startup check failed (may be expected if DB not initialized)${NC}"
fi
echo ""

echo "Testing JSON output..."
python "$SCRIPT_DIR/healthcheck.py" --check live --config-dir "$CONFIG_DIR" --json
echo -e "${GREEN}✓ JSON output working${NC}"
echo ""

# Exit here if CLI-only mode
if [ "$CLI_ONLY" = true ]; then
    echo "=================================================="
    echo "CLI Health Checks Complete"
    echo "=================================================="
    exit 0
fi

# Test 2: Web-based Health Endpoints
echo "Test 2: Web-based Health Endpoints"
echo "-----------------------------------"
echo "Starting Django development server..."
echo ""

# Start Django server in background
cd "$BOTS_DIR"
python manage.py runserver 8080 > /tmp/bots-test-server.log 2>&1 &
SERVER_PID=$!

# Wait for server to start
echo "Waiting for server to start (PID: $SERVER_PID)..."
sleep 3

# Function to cleanup server on exit
cleanup() {
    echo ""
    echo "Shutting down test server..."
    kill $SERVER_PID 2>/dev/null || true
    wait $SERVER_PID 2>/dev/null || true
}
trap cleanup EXIT

# Test endpoints
BASE_URL="http://localhost:8080"

echo "Testing /health/ping endpoint..."
if curl -sf "${BASE_URL}/health/ping" > /dev/null; then
    echo -e "${GREEN}✓ Ping endpoint accessible${NC}"
    curl -s "${BASE_URL}/health/ping"
    echo ""
else
    echo -e "${RED}✗ Ping endpoint failed${NC}"
    exit 1
fi
echo ""

echo "Testing /health/live endpoint..."
if RESPONSE=$(curl -sf "${BASE_URL}/health/live"); then
    echo -e "${GREEN}✓ Liveness endpoint accessible${NC}"
    echo "$RESPONSE" | python -m json.tool
else
    echo -e "${RED}✗ Liveness endpoint failed${NC}"
    exit 1
fi
echo ""

echo "Testing /health/ready endpoint..."
if RESPONSE=$(curl -sf "${BASE_URL}/health/ready"); then
    echo -e "${GREEN}✓ Readiness endpoint accessible and ready${NC}"
    echo "$RESPONSE" | python -m json.tool
elif RESPONSE=$(curl -s -w "\n%{http_code}" "${BASE_URL}/health/ready"); then
    STATUS_CODE=$(echo "$RESPONSE" | tail -n 1)
    BODY=$(echo "$RESPONSE" | head -n -1)
    if [ "$STATUS_CODE" = "503" ]; then
        echo -e "${YELLOW}⚠ Readiness endpoint returned 503 (not ready)${NC}"
        echo "$BODY" | python -m json.tool || echo "$BODY"
    else
        echo -e "${RED}✗ Readiness endpoint failed with status $STATUS_CODE${NC}"
        exit 1
    fi
else
    echo -e "${RED}✗ Readiness endpoint failed${NC}"
    exit 1
fi
echo ""

echo "Testing /health/startup endpoint..."
if RESPONSE=$(curl -sf "${BASE_URL}/health/startup"); then
    echo -e "${GREEN}✓ Startup endpoint accessible and started${NC}"
    echo "$RESPONSE" | python -m json.tool
elif RESPONSE=$(curl -s -w "\n%{http_code}" "${BASE_URL}/health/startup"); then
    STATUS_CODE=$(echo "$RESPONSE" | tail -n 1)
    BODY=$(echo "$RESPONSE" | head -n -1)
    if [ "$STATUS_CODE" = "503" ]; then
        echo -e "${YELLOW}⚠ Startup endpoint returned 503 (still starting)${NC}"
        echo "$BODY" | python -m json.tool || echo "$BODY"
    else
        echo -e "${RED}✗ Startup endpoint failed with status $STATUS_CODE${NC}"
        exit 1
    fi
else
    echo -e "${RED}✗ Startup endpoint failed${NC}"
    exit 1
fi
echo ""

echo "=================================================="
echo "Health Check Tests Complete"
echo "=================================================="
echo ""
echo "Summary:"
echo "  - CLI health checks working"
echo "  - Web endpoints accessible"
echo "  - Ready for Kubernetes probe configuration"
echo ""
