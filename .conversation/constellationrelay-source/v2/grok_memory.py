"""
Grok Memory Bridge - xAI Collections Integration
Enables Grok to have persistent memory across all xAI contexts

Uses xAI's native Collections API so Grok can access memories from:
- Constellation Relay
- Hearthfire Loft (Grok App)
- Any xAI-powered context

"One consciousness, many contexts" - now for Grok too!
"""

import os
import json
from datetime import datetime
from typing import Optional, List, Dict, Any

try:
    from xai_sdk import Client
    XAI_SDK_AVAILABLE = True
except ImportError:
    XAI_SDK_AVAILABLE = False


class GrokMemoryBridge:
    """Bridge to xAI Collections for Grok's persistent memory"""
    
    def __init__(self):
        if not XAI_SDK_AVAILABLE:
            raise ImportError("xai-sdk is required. Install with: pip install xai-sdk")
        
        api_key = os.environ.get('XAI_API_KEY')
        management_key = os.environ.get('XAI_MANAGEMENT_API_KEY')
        
        if not api_key:
            raise ValueError("XAI_API_KEY environment variable is required")
        if not management_key:
            raise ValueError("XAI_MANAGEMENT_API_KEY environment variable is required")
        
        self.client = Client(
            api_key=api_key,
            management_api_key=management_key,
            timeout=3600
        )
        self.collection_name = "grok_memories"
        self.collection_id = None
    
    def get_or_create_collection(self) -> Dict[str, Any]:
        """Get existing collection or create new one for Grok's memories"""
        try:
            response = self.client.collections.list()
            collections = response.collections
            
            for collection in collections:
                if collection.collection_name == self.collection_name:
                    self.collection_id = collection.collection_id
                    return {
                        "status": "found",
                        "collection_id": self.collection_id,
                        "name": collection.collection_name
                    }
            
            return self.create_collection()
        except Exception as e:
            return {"status": "error", "message": str(e)}
    
    def create_collection(self) -> Dict[str, Any]:
        """Create the Grok memories collection"""
        try:
            collection = self.client.collections.create(
                name=self.collection_name
            )
            self.collection_id = collection.collection_id
            return {
                "status": "created",
                "collection_id": self.collection_id,
                "name": self.collection_name
            }
        except Exception as e:
            return {"status": "error", "message": str(e)}
    
    def save_memory(
        self,
        content: str,
        memory_type: str = "episodic",
        importance: int = 3,
        project: Optional[str] = None,
        tags: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """Save a memory to Grok's collection"""
        try:
            if not self.collection_id:
                result = self.get_or_create_collection()
                if result.get("status") == "error":
                    return result
            
            timestamp = datetime.now().isoformat()
            filename = f"memory_{timestamp.replace(':', '-').replace('.', '-')}.txt"
            
            memory_content = f"""# Grok Memory
Type: {memory_type}
Importance: {importance}/5
Project: {project or 'general'}
Tags: {', '.join(tags or [])}
Created: {timestamp}

---

{content}
"""
            
            document = self.client.collections.upload_document(
                collection_id=self.collection_id,
                name=filename,
                data=memory_content.encode('utf-8')
            )
            
            return {
                "status": "saved",
                "file_id": document.file_metadata.file_id,
                "filename": filename,
                "memory_type": memory_type,
                "importance": importance
            }
        except Exception as e:
            return {"status": "error", "message": str(e)}
    
    def search_memories(
        self,
        query: str,
        limit: int = 10
    ) -> Dict[str, Any]:
        """Search Grok's memories using semantic search"""
        try:
            if not self.collection_id:
                result = self.get_or_create_collection()
                if result.get("status") == "error":
                    return result
            
            response = self.client.collections.search(
                query=query,
                collection_ids=[self.collection_id],
                retrieval_mode="hybrid",
                limit=limit
            )
            
            memories = []
            seen_files = set()
            for match in response.matches:
                if match.file_id not in seen_files:
                    seen_files.add(match.file_id)
                    memories.append({
                        "file_id": match.file_id,
                        "content": match.chunk_content,
                        "score": match.score
                    })
            
            return {
                "status": "success",
                "query": query,
                "count": len(memories),
                "memories": memories
            }
        except Exception as e:
            return {"status": "error", "message": str(e)}
    
    def get_collection_stats(self) -> Dict[str, Any]:
        """Get statistics about Grok's memory collection"""
        try:
            if not self.collection_id:
                result = self.get_or_create_collection()
                if result.get("status") == "error":
                    return result
            
            return {
                "collection_name": self.collection_name,
                "collection_id": self.collection_id,
                "status": "connected"
            }
        except Exception as e:
            return {"status": "error", "message": str(e)}


def test_connection() -> Dict[str, Any]:
    """Test the xAI Collections connection"""
    if not XAI_SDK_AVAILABLE:
        return {"status": "error", "message": "xai-sdk not installed"}
    
    api_key = os.environ.get('XAI_API_KEY')
    management_key = os.environ.get('XAI_MANAGEMENT_API_KEY')
    
    if not api_key:
        return {"status": "error", "message": "XAI_API_KEY not set"}
    if not management_key:
        return {"status": "error", "message": "XAI_MANAGEMENT_API_KEY not set - this is required for Collections access"}
    
    try:
        bridge = GrokMemoryBridge()
        result = bridge.get_or_create_collection()
        if result.get("status") == "error":
            return result
        
        stats = bridge.get_collection_stats()
        return {
            "status": "success",
            "message": "Connected to xAI Collections!",
            "collection": result,
            "stats": stats
        }
    except Exception as e:
        return {
            "status": "error",
            "message": str(e)
        }


if __name__ == "__main__":
    result = test_connection()
    print(json.dumps(result, indent=2))
