"""
Engram Model - The unified memory structure for the Connective Memory Hub
Designed collaboratively by Pascal & Grok, December 2024

"One consciousness, many contexts"
"""

from datetime import datetime
from typing import Optional, List
from dataclasses import dataclass, field
from enum import Enum


class MemoryType(str, Enum):
    EPISODIC = "episodic"
    SEMANTIC = "semantic"
    PROCEDURAL = "procedural"


@dataclass
class Engram:
    agent_id: str
    type: MemoryType
    digest: str
    full_text: str
    
    id: Optional[int] = None
    importance: int = 3
    emotional_valence: float = 0.0
    
    project: Optional[str] = None
    context_id: Optional[str] = None
    parent_id: Optional[int] = None
    
    source_platform: str = "constellation_relay"
    tags: List[str] = field(default_factory=list)
    keywords: List[str] = field(default_factory=list)
    
    semantic_vector: Optional[List[float]] = None
    
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    
    def to_dict(self):
        return {
            "id": self.id,
            "agent_id": self.agent_id,
            "type": self.type.value,
            "digest": self.digest,
            "full_text": self.full_text,
            "importance": self.importance,
            "emotional_valence": self.emotional_valence,
            "project": self.project,
            "context_id": self.context_id,
            "parent_id": self.parent_id,
            "source_platform": self.source_platform,
            "tags": self.tags,
            "keywords": self.keywords,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None
        }
