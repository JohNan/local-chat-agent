import sys

with open('/codebase/Dockerfile', 'r') as f:
    content = f.read()

# First we need to remove the bad RUN line
lines = content.split('\n')
new_lines = []
skip = False
for line in lines:
    if line.startswith('# Install gh CLI'):
        new_lines.append(line)
        skip = True
        continue
    if skip:
        if line == '' or line.startswith('# Install Language Servers'):
            skip = False
        else:
            continue
    new_lines.append(line)

content = '\n'.join(new_lines)

gh_install = """RUN mkdir -p -m 755 /etc/apt/keyrings \\
    && curl -fsSL https://cli.github.com/packages/githubcli-archive-keyring.gpg | dd of=/etc/apt/keyrings/githubcli-archive-keyring.gpg \\
    && chmod go+r /etc/apt/keyrings/githubcli-archive-keyring.gpg \\
    && echo "deb [arch=amd64 signed-by=/etc/apt/keyrings/githubcli-archive-keyring.gpg] https://cli.github.com/packages stable main" | tee /etc/apt/sources.list.d/github-cli.list > /dev/null \\
    && apt-get update \\
    && apt-get install gh -y \\
    && rm -rf /var/lib/apt/lists/*

"""

content = content.replace('# Install gh CLI\n', '# Install gh CLI\n' + gh_install)

with open('/codebase/Dockerfile', 'w') as f:
    f.write(content)

