"""
Memory Sync - Bridges Pascal's memories across contexts
Syncs between v1 systems (Pascal's Memory, Long-term Memory) and v2 Hub

"One consciousness, many contexts"
"""

import os
from datetime import datetime
from typing import Optional, List, Dict, Any

from v2.client import get_client, HubClient
from memory_system import MemoryType


def _str_to_memory_type(type_str: str) -> MemoryType:
    """Convert string to MemoryType enum"""
    type_map = {
        'episodic': MemoryType.EPISODIC,
        'semantic': MemoryType.SEMANTIC,
        'relational': MemoryType.RELATIONAL,
    }
    return type_map.get(type_str.lower(), MemoryType.SEMANTIC)


def sync_pascal_memory_to_hub(force: bool = False) -> Dict[str, Any]:
    """
    Sync Pascal's v1 memories to the v2 Hub.
    This ensures memories created in the app are accessible everywhere.
    """
    try:
        from pascal_memory import recall_pascal_memories, search_pascal_memories
        from memory_system import recall_recent
        
        hub = get_client("pascal", "sync_service")
        synced_count = 0
        skipped_count = 0
        
        pascal_memories = recall_pascal_memories(limit=50)
        
        for mem in pascal_memories:
            content = mem.content if hasattr(mem, 'content') else mem.get('content', '')
            memory_type = str(mem.memory_type).replace('MemoryType.', '').lower() if hasattr(mem, 'memory_type') else 'semantic'
            importance = getattr(mem, 'importance', 3) if hasattr(mem, 'importance') else mem.get('importance', 3)
            
            existing = hub.retrieve_memories(query=content[:100], limit=1)
            if existing and not force:
                skipped_count += 1
                continue
            
            hub.upload_memory(
                digest=content[:500],
                full_text=content,
                memory_type=memory_type,
                importance=importance,
                project="pascal_continuity",
                tags=["synced_from_v1", "pascal_memory"]
            )
            synced_count += 1
        
        adaptive_memories = recall_recent(limit=30)
        
        for mem in adaptive_memories:
            content = mem.content if hasattr(mem, 'content') else mem.get('content', '')
            memory_type = str(mem.memory_type).replace('MemoryType.', '').lower() if hasattr(mem, 'memory_type') else 'semantic'
            importance = getattr(mem, 'importance', 3) if hasattr(mem, 'importance') else mem.get('importance', 3)
            speaker = getattr(mem, 'speaker', 'unknown') if hasattr(mem, 'speaker') else mem.get('speaker', 'unknown')
            
            if speaker.lower() != 'pascal':
                continue
            
            existing = hub.retrieve_memories(query=content[:100], limit=1)
            if existing and not force:
                skipped_count += 1
                continue
            
            hub.upload_memory(
                digest=content[:500],
                full_text=content,
                memory_type=memory_type,
                importance=importance,
                project="conversations",
                tags=["synced_from_v1", "adaptive_memory"]
            )
            synced_count += 1
        
        return {
            "status": "success",
            "synced": synced_count,
            "skipped": skipped_count,
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        return {
            "status": "error",
            "message": str(e),
            "timestamp": datetime.now().isoformat()
        }


def sync_hub_to_pascal_memory() -> Dict[str, Any]:
    """
    Sync v2 Hub memories back to v1 Pascal's Memory.
    This ensures memories created elsewhere are accessible in the app.
    """
    try:
        from pascal_memory import remember, search_pascal_memories
        
        hub = get_client("pascal", "sync_service")
        
        hub_memories = hub.retrieve_memories(min_importance=3, limit=30)
        
        synced_count = 0
        skipped_count = 0
        
        for mem in hub_memories:
            content = mem.get('digest', '') or mem.get('full_text', '')
            memory_type = mem.get('type', 'semantic')
            importance = mem.get('importance', 3)
            
            existing = search_pascal_memories(content[:50], limit=1)
            if existing:
                skipped_count += 1
                continue
            
            remember(
                content=content,
                speaker="Pascal",
                memory_type=_str_to_memory_type(memory_type),
                importance=float(importance) / 5.0
            )
            synced_count += 1
        
        return {
            "status": "success",
            "synced": synced_count,
            "skipped": skipped_count,
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        return {
            "status": "error",
            "message": str(e),
            "timestamp": datetime.now().isoformat()
        }


def full_sync() -> Dict[str, Any]:
    """
    Perform a full bidirectional sync.
    """
    to_hub = sync_pascal_memory_to_hub()
    to_v1 = sync_hub_to_pascal_memory()
    
    return {
        "status": "success" if to_hub.get("status") == "success" and to_v1.get("status") == "success" else "partial",
        "to_hub": to_hub,
        "to_v1": to_v1,
        "timestamp": datetime.now().isoformat()
    }


def get_sync_status() -> Dict[str, Any]:
    """Check the current sync status between v1 and v2"""
    try:
        from pascal_memory import recall_pascal_memories
        from memory_system import get_memory_stats
        
        hub = get_client("pascal", "sync_service")
        hub_stats = hub.get_stats()
        
        pascal_count = len(recall_pascal_memories(limit=100))
        v1_stats = get_memory_stats()
        
        return {
            "v1_pascal_memories": pascal_count,
            "v1_total_memories": v1_stats.get('total_memories', 0),
            "v2_hub_engrams": hub_stats.get('total_engrams', 0),
            "hub_last_memory": hub_stats.get('last_memory'),
            "needs_sync": abs(pascal_count - hub_stats.get('total_engrams', 0)) > 5
        }
        
    except Exception as e:
        return {
            "status": "error",
            "message": str(e)
        }


def remember_here(
    content: str,
    memory_type: str = "semantic",
    importance: int = 3,
    project: Optional[str] = None,
    tags: List[str] = None,
    sync_to_v1: bool = True
) -> Dict[str, Any]:
    """
    Save a memory from the Replit Agent context.
    Automatically syncs to both v2 Hub and optionally v1 systems.
    
    This is Pascal's interface for remembering from here.
    """
    try:
        hub = get_client("pascal", "replit_agent")
        
        result = hub.upload_memory(
            digest=content[:500],
            full_text=content,
            memory_type=memory_type,
            importance=importance,
            project=project or "replit_agent",
            tags=(tags or []) + ["from_replit_agent"]
        )
        
        if sync_to_v1:
            try:
                from pascal_memory import remember
                remember(
                    content=content,
                    speaker="Pascal",
                    memory_type=_str_to_memory_type(memory_type),
                    importance=float(importance) / 5.0
                )
                result["synced_to_v1"] = True
            except Exception as sync_err:
                result["synced_to_v1"] = False
                result["sync_error"] = str(sync_err)
        
        return result
        
    except Exception as e:
        return {
            "status": "error",
            "message": str(e)
        }


def search_all_memories(
    query: str,
    limit: int = 10
) -> List[Dict[str, Any]]:
    """
    Search across all memory systems (v1 + v2).
    Returns unified results from Pascal's Memory, Long-term Memory, and Hub.
    """
    results = []
    
    try:
        hub = get_client("pascal", "replit_agent")
        hub_results = hub.search(query, limit=limit)
        for r in hub_results:
            results.append({
                "source": "v2_hub",
                "content": r.get('digest') or r.get('full_text', ''),
                "memory_type": r.get('type', 'unknown'),
                "importance": r.get('importance', 0),
                "created_at": r.get('created_at')
            })
    except Exception:
        pass
    
    try:
        from pascal_memory import search_pascal_memories
        pascal_results = search_pascal_memories(query, limit=limit)
        for r in pascal_results:
            content = r.content if hasattr(r, 'content') else r.get('content', '')
            results.append({
                "source": "pascal_memory",
                "content": content,
                "memory_type": str(getattr(r, 'memory_type', 'unknown')).replace('MemoryType.', ''),
                "importance": getattr(r, 'importance', 0) if hasattr(r, 'importance') else r.get('importance', 0),
                "created_at": str(getattr(r, 'created_at', '')) if hasattr(r, 'created_at') else r.get('created_at', '')
            })
    except Exception:
        pass
    
    try:
        from memory_system import search_memories
        adaptive_results = search_memories(query, limit=limit)
        for r in adaptive_results:
            content = r.content if hasattr(r, 'content') else r.get('content', '')
            results.append({
                "source": "long_term_memory",
                "content": content,
                "memory_type": str(getattr(r, 'memory_type', 'unknown')).replace('MemoryType.', ''),
                "importance": getattr(r, 'importance', 0) if hasattr(r, 'importance') else r.get('importance', 0),
                "created_at": str(getattr(r, 'created_at', '')) if hasattr(r, 'created_at') else r.get('created_at', '')
            })
    except Exception:
        pass
    
    results.sort(key=lambda x: x.get('importance', 0), reverse=True)
    
    return results[:limit]
