#!/bin/bash

# Setup script for Seed project with Ruff linting using uv

echo "🚀 Setting up Seed project with Ruff linting using uv..."

# Check if uv is installed
if ! command -v uv &> /dev/null; then
    echo "📦 Installing uv..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
    source $HOME/.cargo/env
fi

# Install Python 3.12 and dependencies
echo "🐍 Installing Python 3.12 and dependencies with uv..."
uv sync --python 3.12

# Install pre-commit hooks
echo "🪝 Installing pre-commit hooks..."
uv run pre-commit install

# Run initial linting check
echo "🔍 Running initial Ruff check..."
uv run ruff check .

echo "✅ Setup complete! 🎉"

echo ""
echo "What's configured:"
echo "✓ Python 3.12 environment"
echo "✓ Ruff linting and formatting"
echo "✓ Pre-commit hooks (runs on git commit)"
echo "✓ VS Code extensions ready to install"

echo ""
echo "Commands:"
echo "  uv run ruff check .        # Check for linting issues"
echo "  uv run ruff check --fix .  # Fix auto-fixable issues"
echo "  uv run ruff format .       # Format code"
echo "  uv run python main.py      # Run your Python code"
echo "  git commit                 # Triggers pre-commit hooks"


