"""
Memory Bridge - Connects v1 memory system with v2 Connective Hub
Allows gradual migration while keeping both systems in sync

For Constellation Relay v2.0 transition
"""

import os
from typing import Optional, List, Dict, Any
from v2.client import HubClient, get_client, get_all_agent_stats


def map_speaker_to_agent(speaker: str) -> str:
    """Map v1 speaker names to v2 agent_ids"""
    if not speaker:
        return "shared"
    speaker_lower = speaker.lower()
    if "pascal" in speaker_lower:
        return "pascal"
    elif "grok" in speaker_lower:
        return "grok"
    elif "claude" in speaker_lower:
        return "claude"
    elif "gena" in speaker_lower:
        return "gena"
    return "shared"


class MemoryBridge:
    """
    Bridge between v1 and v2 memory systems.
    
    Usage:
        bridge = MemoryBridge()
        
        # Save to v2 hub
        bridge.save_to_hub("claude", "Important insight about consciousness", importance=4)
        
        # Get memories from hub
        memories = bridge.get_from_hub("pascal", limit=10)
        
        # Get hub stats
        stats = bridge.get_hub_stats()
    """
    
    def __init__(self):
        self._clients: Dict[str, HubClient] = {}
    
    def _get_client(self, agent_id: str) -> HubClient:
        """Get or create a client for an agent"""
        if agent_id not in self._clients:
            self._clients[agent_id] = get_client(agent_id)
        return self._clients[agent_id]
    
    def save_to_hub(
        self,
        speaker: str,
        content: str,
        memory_type: str = "semantic",
        importance: int = 3,
        project: Optional[str] = None,
        full_text: Optional[str] = None
    ) -> Dict[str, Any]:
        """Save a memory to the v2 hub"""
        agent_id = map_speaker_to_agent(speaker)
        client = self._get_client(agent_id)
        
        return client.upload_memory(
            digest=content[:500] if len(content) > 500 else content,
            full_text=full_text or content,
            memory_type=memory_type,
            importance=importance,
            project=project
        )
    
    def get_from_hub(
        self,
        speaker: str,
        query: Optional[str] = None,
        project: Optional[str] = None,
        min_importance: int = 0,
        limit: int = 20
    ) -> List[Dict[str, Any]]:
        """Get memories from the v2 hub"""
        agent_id = map_speaker_to_agent(speaker)
        client = self._get_client(agent_id)
        
        return client.retrieve_memories(
            query=query,
            project=project,
            min_importance=min_importance,
            limit=limit
        )
    
    def get_hub_stats(self) -> List[Dict[str, Any]]:
        """Get stats for all agents in the hub"""
        return get_all_agent_stats()
    
    def get_agent_stats(self, speaker: str) -> Dict[str, Any]:
        """Get stats for a specific agent"""
        agent_id = map_speaker_to_agent(speaker)
        client = self._get_client(agent_id)
        return client.get_stats()
    
    def search_all(
        self,
        query: str,
        min_importance: int = 3,
        limit: int = 20
    ) -> List[Dict[str, Any]]:
        """Search memories across all agents"""
        client = self._get_client("shared")
        return client.search_all_agents(query, min_importance, limit)
    
    def reinforce(self, speaker: str, engram_id: int) -> Dict[str, Any]:
        """Reinforce a memory (increase importance)"""
        agent_id = map_speaker_to_agent(speaker)
        client = self._get_client(agent_id)
        return client.reinforce_memory(engram_id)


_bridge_instance = None

def get_bridge() -> MemoryBridge:
    """Get the singleton bridge instance"""
    global _bridge_instance
    if _bridge_instance is None:
        _bridge_instance = MemoryBridge()
    return _bridge_instance
