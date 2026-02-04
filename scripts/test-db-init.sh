#!/bin/bash
# Quick test script for database initialization

set -e

echo "=========================================="
echo "Testing Bots-EDI Database Initialization"
echo "=========================================="
echo

# Activate conda environment
echo "Activating botsedi conda environment..."
eval "$(conda shell.bash hook)"
conda activate botsedi

# Test with SQLite (default test config)
echo "Test 1: SQLite database initialization"
echo "--------------------------------------"
python scripts/init-database.py --config-dir=/tmp/bots_test/config

echo
echo "✓ Test 1 passed!"
echo

# Test idempotency - run again
echo "Test 2: Idempotency check (re-run on existing DB)"
echo "--------------------------------------"
python scripts/init-database.py --config-dir=/tmp/bots_test/config

echo
echo "✓ Test 2 passed!"
echo

# Verify database
echo "Test 3: Verify database contents"
echo "--------------------------------------"
sqlite3 /tmp/bots_test/botssys/sqlitedb/test-botsdb ".tables"

echo
echo "=========================================="
echo "✓ All tests passed!"
echo "=========================================="
