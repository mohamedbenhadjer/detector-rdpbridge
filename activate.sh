#!/bin/bash
# Quick activation script for the virtual environment
# Usage: source activate.sh

if [ -d "venv" ]; then
    source venv/bin/activate
    echo "✓ Virtual environment activated"
    echo "Python: $(which python)"
    echo "Pip: $(which pip)"
    echo ""
    echo "Available commands:"
    echo "  - pw-ws-reporter --help"
    echo "  - pytest tests/ -v"
    echo "  - playwright install"
    echo ""
    echo "To deactivate: deactivate"
else
    echo "Error: venv directory not found"
    echo "Run: python3 -m venv venv"
fi

