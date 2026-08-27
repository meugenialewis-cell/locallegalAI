"""
Generate a secure Pascal token for Claude Code
Run this after setting up HUB_SECRET
"""

import os
from v2.auth import create_agent_token

def main():
    hub_secret = os.environ.get('HUB_SECRET')
    
    if not hub_secret or hub_secret == "constellation-relay-hub-secret-change-in-prod":
        print("ERROR: HUB_SECRET not set or using default value!")
        print("Please set a secure HUB_SECRET environment variable first.")
        return
    
    print(f"HUB_SECRET is set (first 10 chars): {hub_secret[:10]}...")
    print()
    
    # Generate token for Pascal
    token = create_agent_token('pascal', 'claude_code', long_lived=True)
    
    print("="*60)
    print("SECURE PASCAL TOKEN FOR CLAUDE CODE")
    print("="*60)
    print()
    print(f"Token: {token}")
    print()
    print("="*60)
    print("This token is signed with your secure HUB_SECRET")
    print("Valid for 1 year")
    print("="*60)
    
    # Also print connection instructions
    print()
    print("CONNECTION INSTRUCTIONS FOR CLAUDE CODE:")
    print("-"*60)
    print(f"""
# Constellation Relay - Memory Hub Connection

## Your Credentials
- Agent ID: pascal
- Token: {token}
- Hub URL: [Your published Replit URL]

## Save a Memory
```python
import requests

HUB_URL = "https://YOUR-REPLIT-APP.replit.app"
TOKEN = "{token}"

response = requests.post(
    f"{{HUB_URL}}/engrams/upload",
    headers={{"Authorization": f"Bearer {{TOKEN}}"}},
    json={{
        "digest": "Memory content here",
        "importance": 3,
        "type": "semantic"
    }}
)
print(response.json())
```

## Retrieve Memories
```python
response = requests.get(
    f"{{HUB_URL}}/engrams/retrieve",
    headers={{"Authorization": f"Bearer {{TOKEN}}"}},
    params={{"limit": 10}}
)
print(response.json())
```
""")

if __name__ == "__main__":
    main()
