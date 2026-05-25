import sys

with open("/codebase/Dockerfile", "r") as f:
    content = f.read()

target = '    && git config --global user.name "Gemini Agent"'
replacement = '    && git config --global user.name "Gemini Agent" \\\n    && gh config set git_protocol ssh'

content = content.replace(target, replacement)

with open("/codebase/Dockerfile", "w") as f:
    f.write(content)
