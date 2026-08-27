"""
Generate long-lived tokens for external access to the Connective Hub

Usage:
    python v2/generate_token.py claude claude_code
    python v2/generate_token.py grok api
    python v2/generate_token.py pascal replit
"""

import sys
from v2.auth import create_agent_token

def main():
    if len(sys.argv) < 3:
        print("Usage: python v2/generate_token.py <agent_id> <platform>")
        print("Example: python v2/generate_token.py claude claude_code")
        sys.exit(1)
    
    agent_id = sys.argv[1]
    platform = sys.argv[2]
    
    token = create_agent_token(agent_id, platform, long_lived=True)
    
    print(f"\n🔐 Token generated for {agent_id} on {platform}")
    print(f"   Valid for 365 days\n")
    print(f"Token: {token}\n")

if __name__ == "__main__":
    main()
