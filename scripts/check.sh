#!/usr/bin/env bash
set -euo pipefail

echo "==> 1. Checking formatting (Black)..."
black --check src tests

echo "==> 2. Checking lint rules (Ruff)..."
ruff check src tests

echo "==> 3. Checking static typing (mypy)..."
mypy src/running_data

echo "==> 4. Running tests and coverage (pytest)..."
pytest --cov=src/running_data --cov-report=term-missing -W error tests

echo "==> All quality gates passed successfully!"
