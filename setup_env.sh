#!/bin/bash
set -e  # Stop immediately if a step fails

echo "🛠️  Setting up Python environment for Gemini Agent..."

# 1. Create and activate a virtual environment (Best Practice)
if [ ! -d "venv" ]; then
    python3 -m venv venv
fi
source venv/bin/activate

# 2. Upgrade pip
pip install --upgrade pip

# 3. Install dependencies from file
if [ -f "requirements.txt" ]; then
    pip install -r requirements.txt
else
    # Fallback if file not created yet (first run)
    pip install flask google-genai markdown
fi

# 4. Install tools for code quality (Important for Jules!)
# 'black' formats code automatically
# 'pylint' finds errors
pip install black pylint

echo "✅ Environment ready! Active venv and dependencies installed."
