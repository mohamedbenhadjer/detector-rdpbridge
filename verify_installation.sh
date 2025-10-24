#!/bin/bash
# Verification script for pw-ws-reporter installation

set -e

echo "========================================="
echo "Verifying pw-ws-reporter Installation"
echo "========================================="
echo ""

echo "1. Checking Python version..."
python_version=$(python3 --version)
echo "   ✓ $python_version"
echo ""

echo "2. Checking if package is installed..."
if pip show pw-ws-reporter > /dev/null 2>&1; then
    echo "   ✓ pw-ws-reporter is installed"
else
    echo "   ✗ pw-ws-reporter not found"
    echo "   Run: pip install -e ."
    exit 1
fi
echo ""

echo "3. Checking CLI availability..."
if command -v pw-ws-reporter > /dev/null 2>&1; then
    echo "   ✓ pw-ws-reporter CLI is available"
else
    echo "   ✗ pw-ws-reporter CLI not found"
    exit 1
fi
echo ""

echo "4. Testing CLI commands..."
pw-ws-reporter --help > /dev/null 2>&1 && echo "   ✓ pw-ws-reporter --help works"
pw-ws-reporter run --help > /dev/null 2>&1 && echo "   ✓ pw-ws-reporter run --help works"
pw-ws-reporter send --help > /dev/null 2>&1 && echo "   ✓ pw-ws-reporter send --help works"
echo ""

echo "5. Checking module imports..."
python3 -c "import pw_ws_reporter" && echo "   ✓ Can import pw_ws_reporter"
python3 -c "from pw_ws_reporter import report_errors_to_flutter" && echo "   ✓ Can import report_errors_to_flutter"
python3 -c "from pw_ws_reporter.ws_client import WsClient" && echo "   ✓ Can import WsClient"
python3 -c "from pw_ws_reporter.pytest_plugin import pytest_configure" && echo "   ✓ Can import pytest plugin"
echo ""

echo "6. Running test suite..."
if pytest tests/ -q --tb=line; then
    echo "   ✓ All tests passed"
else
    echo "   ✗ Some tests failed"
    exit 1
fi
echo ""

echo "========================================="
echo "✓ Installation verification complete!"
echo "========================================="
echo ""
echo "Next steps:"
echo "  1. Start your Flutter app with WebSocket server"
echo "  2. Run your Playwright tests with: pytest tests/"
echo "  3. Or use the CLI: pw-ws-reporter run pytest tests/"
echo "  4. See QUICKSTART.md for more examples"
echo ""

