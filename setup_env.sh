#!/bin/bash
set -e  # Stop immediately if a step fails

echo "🛠️  Setting up Python environment for Gemini Agent..."

# 1. Install uv if not present
if ! command -v uv &> /dev/null; then
    echo "Installing uv..."
    pip install uv
fi

# 2. Create virtual environment using uv
echo "Creating virtual environment..."
uv venv venv

# 3. Activate venv
source venv/bin/activate

# 4. Install dependencies using uv
if [ -f "requirements.txt" ]; then
    echo "Installing dependencies..."
    uv pip install -r requirements.txt
else
    echo "requirements.txt not found. Installing default packages..."
    uv pip install flask google-genai markdown
fi

# 5. Install dev tools
echo "Installing dev tools..."
uv pip install black pylint

echo "✅ Environment ready! Run 'source venv/bin/activate' to start."
