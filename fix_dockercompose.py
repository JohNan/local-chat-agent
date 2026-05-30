import re

with open('docker-compose.example.yml', 'r') as f:
    content = f.read()

# Add ~/.config/gh to volumes
if '~/.config/gh' not in content:
    content = content.replace(
        '      - ${SSH_AUTH_SOCK}:/ssh-agent',
        '      - ${SSH_AUTH_SOCK}:/ssh-agent\n      # Uncomment to share GitHub CLI credentials from your host machine\n      # - ~/.config/gh:/root/.config/gh'
    )

# Add GH_TOKEN to environment
if 'GH_TOKEN' not in content:
    content = content.replace(
        '      - GOOGLE_API_KEY',
        '      - GOOGLE_API_KEY\n      # - GH_TOKEN # Uncomment and set in your .env file to authenticate GitHub CLI without mounting config'
    )

with open('docker-compose.example.yml', 'w') as f:
    f.write(content)
