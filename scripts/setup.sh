#!/usr/bin/env bash
# scripts/setup.sh — Linux/macOS setup script for Model Router Evaluation
# Usage: bash scripts/setup.sh

set -euo pipefail

echo "=== Microsoft Foundry Model Router Evaluation — Setup ==="

# Check Python
if ! command -v python3 &> /dev/null; then
    echo "ERROR: python3 not found. Install Python 3.9+ first."
    exit 1
fi

PY_VERSION=$(python3 --version)
echo "Found $PY_VERSION"

# Create virtual environment if it doesn't exist
if [ ! -d ".venv" ]; then
    echo "Creating virtual environment (.venv)..."
    python3 -m venv .venv
fi

# Activate
echo "Activating virtual environment..."
source .venv/bin/activate

# Upgrade pip
echo "Upgrading pip..."
python -m pip install --upgrade pip --quiet

# Install project with dev dependencies
echo "Installing project and dependencies..."
pip install -e ".[dev]" --quiet

# Copy .env.example if .env doesn't exist
if [ ! -f ".env" ] && [ -f ".env.example" ]; then
    cp .env.example .env
    echo "Created .env from .env.example — edit it with your API keys."
fi

echo ""
echo "=== Setup complete ==="
echo ""
echo "Next steps:"
echo "  1. Edit .env with your Azure endpoints and API keys"
echo "  2. Run:  python scripts/run_eval.py --dry-run"
echo "  3. Run:  python scripts/run_eval.py"
echo ""
echo "Optional — Foundry cloud evaluation:"
echo "  4. pip install -e '.[foundry]'"
echo "  5. az login"
echo "  6. Add AZURE_AI_PROJECT_ENDPOINT to .env"
echo "  7. python scripts/run_foundry_eval.py --input-dir results/full-eval"
echo ""
