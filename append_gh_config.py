import sys

with open("/codebase/Dockerfile", "r") as f:
    content = f.read()

TARGET = '    && git config --global user.name "Gemini Agent"'
REPLACEMENT = '    && git config --global user.name "Gemini Agent" \\\n    && gh config set git_protocol ssh'

content = content.replace(TARGET, REPLACEMENT)

with open("/codebase/Dockerfile", "w") as f:
    f.write(content)
