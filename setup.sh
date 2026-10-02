#!/usr/bin/env bash
set -e

echo "=== RAG Project Environment Setup ==="

# Check if python3 is available
if ! command -v python3 &> /dev/null; then
    echo "Error: python3 is not found."
    echo "Please install Python or Xcode Command Line Tools first."
    exit 1
fi

PYTHON_VER=$(python3 --version 2>&1 || true)
if [[ "$PYTHON_VER" == *"xcode-select"* ]]; then
    echo "Error: Xcode Command Line Tools are missing."
    echo "Please complete the Xcode tools installation or run: xcode-select --install"
    exit 1
fi

echo "Found: $PYTHON_VER"

# Create virtual environment if it doesn't exist
if [ ! -d ".venv" ]; then
    echo "Creating virtual environment in .venv/ ..."
    python3 -m venv .venv
    echo "Virtual environment created."
else
    echo "Virtual environment .venv/ already exists."
fi

# Activate virtual environment
echo "Activating virtual environment..."
source .venv/bin/activate

# Upgrade pip
echo "Upgrading pip..."
pip install --upgrade pip

# Install requirements
if [ -f "requirements.txt" ]; then
    echo "Installing dependencies from requirements.txt..."
    pip install -r requirements.txt
    echo "Dependencies installed successfully!"
fi

echo ""
echo "=== Setup Complete! ==="
echo "To activate the environment in your terminal, run:"
echo "    source .venv/bin/activate"
