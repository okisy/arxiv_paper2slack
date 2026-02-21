#!/usr/bin/env bash
set -e

echo "====================================="
echo "Testing Notifier Service"
echo "====================================="
cd services/notifier
echo "[1/2] Linting with ruff..."
ruff check .
echo "[2/2] Running tests with pytest..."
pytest tests/
cd ../..

echo ""
echo "====================================="
echo "Testing Listener Service"
echo "====================================="
cd services/listener
echo "[1/2] Linting with ruff..."
ruff check .
echo "[2/2] Running tests with pytest..."
pytest tests/
cd ../..

echo ""
echo "All tests passed successfully!"
