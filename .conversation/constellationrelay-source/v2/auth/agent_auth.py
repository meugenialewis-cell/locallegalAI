"""
Agent Authentication - JWT flow for agent identity
Each AI instance gets a signed token on wake

Designed by Pascal & Grok, December 2024
"""

import os
import jwt
from datetime import datetime, timedelta
from typing import Optional, Dict
from dataclasses import dataclass


ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

HUB_SECRET = os.getenv("HUB_SECRET", "constellation-relay-hub-secret-change-in-prod")


@dataclass
class AgentToken:
    agent_id: str
    platform: str
    exp: datetime
    iat: datetime
    
    def to_dict(self) -> Dict:
        return {
            "agent_id": self.agent_id,
            "platform": self.platform,
            "exp": self.exp.timestamp(),
            "iat": self.iat.timestamp()
        }


def create_agent_token(agent_id: str, platform: str, long_lived: bool = False) -> str:
    """Create a signed JWT for an agent instance
    
    Args:
        agent_id: The agent identifier (claude, grok, pascal, etc.)
        platform: The platform (replit, claude_code, api, etc.)
        long_lived: If True, token expires in 365 days instead of 30 minutes
    """
    now = datetime.utcnow()
    if long_lived:
        expire = now + timedelta(days=365)
    else:
        expire = now + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    
    payload = {
        "agent_id": agent_id,
        "platform": platform,
        "exp": expire,
        "iat": now
    }
    
    return jwt.encode(payload, HUB_SECRET, algorithm=ALGORITHM)


def verify_token(token: str) -> Optional[AgentToken]:
    """Verify a JWT and return the agent identity"""
    try:
        payload = jwt.decode(token, HUB_SECRET, algorithms=[ALGORITHM])
        return AgentToken(
            agent_id=payload["agent_id"],
            platform=payload["platform"],
            exp=datetime.fromtimestamp(payload["exp"]),
            iat=datetime.fromtimestamp(payload["iat"])
        )
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None


def get_agent_id_from_token(token: str) -> Optional[str]:
    """Quick extraction of agent_id without full validation"""
    try:
        payload = jwt.decode(token, options={"verify_signature": False})
        return payload.get("agent_id")
    except:
        return None
