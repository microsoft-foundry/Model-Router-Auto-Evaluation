#!/usr/bin/env bash
# scripts/demo.sh — Generate mock results and open the dashboard (no API keys needed)
# Usage: bash scripts/demo.sh

set -euo pipefail

echo ""
echo "====================================================="
echo "  Model Router Eval — Demo (no API keys required)"
echo "====================================================="
echo ""
echo "This generates a mock evaluation report with synthetic data"
echo "so you can explore every chart, metric, and output format."
echo ""

# Check Python
if ! command -v python3 &> /dev/null; then
    echo "ERROR: python3 not found. Install Python 3.9+ first."
    exit 1
fi

# Install deps if needed
echo "[1/3] Installing dependencies..."
pip install -e . --quiet 2>/dev/null || pip install -r requirements.txt --quiet

# Generate mock report
OUTPUT_DIR="results/demo"
echo "[2/3] Generating mock evaluation report..."
python3 scripts/generate_sample_report.py --output-dir "$OUTPUT_DIR"

# Open dashboard
DASHBOARD="$OUTPUT_DIR/dashboard.html"
echo "[3/3] Opening dashboard in browser..."
if [ -f "$DASHBOARD" ]; then
    if command -v xdg-open &> /dev/null; then
        xdg-open "$DASHBOARD" 2>/dev/null &
    elif command -v open &> /dev/null; then
        open "$DASHBOARD"
    else
        echo "  Open $DASHBOARD in your browser manually."
    fi
fi

echo ""
echo "====================================================="
echo "  Demo complete! Results in: $OUTPUT_DIR/"
echo "====================================================="
echo ""
echo "Output files:"
ls -1 "$OUTPUT_DIR"
echo ""
echo "Next steps:"
echo "  1. Explore the dashboard.html in your browser"
echo "  2. Review report.md for a text summary"
echo "  3. Ready for live eval? See docs/how-to-run-live-eval.md"
echo ""
