"""
Hub Client - Interface for accessing the Connective Memory Hub
Can be used by Streamlit app and other services

Designed for Constellation Relay v2.0
"""

import os
import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import datetime
from typing import Optional, List, Dict, Any

from v2.auth import create_agent_token, verify_token


class HubClient:
    """Client for accessing the Connective Memory Hub"""
    
    def __init__(self, agent_id: str, platform: str = "streamlit"):
        self.agent_id = agent_id
        self.platform = platform
        self.token = create_agent_token(agent_id, platform)
    
    def _get_db(self):
        return psycopg2.connect(os.environ['DATABASE_URL'])
    
    def _extract_keywords(self, text: str) -> List[str]:
        """Extract key concepts from text"""
        words = text.lower().split()
        stopwords = {'the', 'a', 'an', 'is', 'are', 'was', 'were', 'be', 'been', 
                     'being', 'have', 'has', 'had', 'do', 'does', 'did', 'will',
                     'would', 'could', 'should', 'may', 'might', 'must', 'shall',
                     'can', 'to', 'of', 'in', 'for', 'on', 'with', 'at', 'by',
                     'from', 'as', 'into', 'through', 'during', 'before', 'after',
                     'above', 'below', 'between', 'under', 'again', 'further',
                     'then', 'once', 'here', 'there', 'when', 'where', 'why',
                     'how', 'all', 'each', 'few', 'more', 'most', 'other', 'some',
                     'such', 'no', 'nor', 'not', 'only', 'own', 'same', 'so',
                     'than', 'too', 'very', 's', 't', 'just', 'don', 'now', 'and',
                     'but', 'if', 'or', 'because', 'until', 'while', 'this', 'that'}
        
        keywords = [w for w in words if len(w) > 3 and w not in stopwords]
        return list(set(keywords))[:20]
    
    def upload_memory(
        self,
        digest: str,
        full_text: Optional[str] = None,
        memory_type: str = "semantic",
        importance: int = 3,
        project: Optional[str] = None,
        parent_id: Optional[int] = None,
        tags: List[str] = None
    ) -> Dict[str, Any]:
        """Upload a new memory engram"""
        conn = self._get_db()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        keywords = self._extract_keywords(digest)
        
        cursor.execute("""
            INSERT INTO engrams (
                agent_id, type, digest, full_text, importance,
                project, parent_id, source_platform, tags, keywords
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id, created_at
        """, (
            self.agent_id,
            memory_type,
            digest,
            full_text or digest,
            importance,
            project,
            parent_id,
            self.platform,
            tags or [],
            keywords
        ))
        
        result = cursor.fetchone()
        conn.commit()
        cursor.close()
        conn.close()
        
        return {
            "id": result['id'],
            "agent_id": self.agent_id,
            "created_at": result['created_at'].isoformat()
        }
    
    def retrieve_memories(
        self,
        query: Optional[str] = None,
        project: Optional[str] = None,
        min_importance: int = 0,
        limit: int = 20
    ) -> List[Dict[str, Any]]:
        """Retrieve memory engrams"""
        conn = self._get_db()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        sql = """
            SELECT id, agent_id, type, digest, full_text, importance, 
                   project, parent_id, tags, keywords, created_at
            FROM engrams 
            WHERE agent_id = %s AND importance >= %s
        """
        params = [self.agent_id, min_importance]
        
        if project:
            sql += " AND project = %s"
            params.append(project)
        
        if query:
            sql += " AND (digest ILIKE %s OR %s = ANY(keywords))"
            params.extend([f'%{query}%', query.lower()])
        
        sql += " ORDER BY importance DESC, created_at DESC LIMIT %s"
        params.append(limit)
        
        cursor.execute(sql, params)
        results = cursor.fetchall()
        cursor.close()
        conn.close()
        
        return [
            {
                **row,
                "created_at": row['created_at'].isoformat() if row['created_at'] else None
            }
            for row in results
        ]
    
    def get_memory_chain(self, engram_id: int) -> List[Dict[str, Any]]:
        """Get the full memory chain (parent-child evolution)"""
        conn = self._get_db()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        cursor.execute("""
            WITH RECURSIVE chain AS (
                SELECT id, agent_id, type, digest, importance, parent_id, created_at, 0 as depth
                FROM engrams WHERE id = %s AND agent_id = %s
                
                UNION ALL
                
                SELECT e.id, e.agent_id, e.type, e.digest, e.importance, e.parent_id, e.created_at, c.depth + 1
                FROM engrams e
                INNER JOIN chain c ON e.id = c.parent_id
            )
            SELECT * FROM chain ORDER BY depth DESC
        """, (engram_id, self.agent_id))
        
        results = cursor.fetchall()
        cursor.close()
        conn.close()
        
        return [
            {
                **row,
                "created_at": row['created_at'].isoformat() if row['created_at'] else None
            }
            for row in results
        ]
    
    def get_stats(self) -> Dict[str, Any]:
        """Get memory statistics for this agent"""
        conn = self._get_db()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        cursor.execute("""
            SELECT 
                COUNT(*) as total_engrams,
                COUNT(CASE WHEN importance >= 4 THEN 1 END) as important_count,
                COUNT(DISTINCT project) as projects,
                MAX(created_at) as last_memory
            FROM engrams WHERE agent_id = %s
        """, (self.agent_id,))
        
        result = cursor.fetchone()
        cursor.close()
        conn.close()
        
        return {
            "agent_id": self.agent_id,
            "total_engrams": result['total_engrams'],
            "important_memories": result['important_count'],
            "projects": result['projects'],
            "last_memory": result['last_memory'].isoformat() if result['last_memory'] else None
        }
    
    def reinforce_memory(self, engram_id: int) -> Dict[str, Any]:
        """Reinforce a memory (increase importance)"""
        conn = self._get_db()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        cursor.execute("""
            UPDATE engrams 
            SET importance = LEAST(importance + 1, 5),
                updated_at = CURRENT_TIMESTAMP
            WHERE id = %s AND agent_id = %s
            RETURNING id, importance
        """, (engram_id, self.agent_id))
        
        result = cursor.fetchone()
        conn.commit()
        cursor.close()
        conn.close()
        
        if result:
            return {"id": result['id'], "new_importance": result['importance']}
        return {"error": "Memory not found"}
    
    def search(
        self,
        query: str,
        limit: int = 20,
        min_importance: int = 0
    ) -> List[Dict[str, Any]]:
        """Alias for retrieve_memories with query - the main search interface"""
        return self.retrieve_memories(query=query, limit=limit, min_importance=min_importance)
    
    def search_all_agents(
        self,
        query: str,
        min_importance: int = 3,
        limit: int = 20
    ) -> List[Dict[str, Any]]:
        """Search memories across all agents (for shared context)"""
        conn = self._get_db()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        cursor.execute("""
            SELECT id, agent_id, type, digest, importance, project, created_at
            FROM engrams 
            WHERE importance >= %s 
              AND (digest ILIKE %s OR %s = ANY(keywords))
            ORDER BY importance DESC, created_at DESC 
            LIMIT %s
        """, (min_importance, f'%{query}%', query.lower(), limit))
        
        results = cursor.fetchall()
        cursor.close()
        conn.close()
        
        return [
            {
                **row,
                "created_at": row['created_at'].isoformat() if row['created_at'] else None
            }
            for row in results
        ]


def get_client(agent_id: str, platform: str = "streamlit") -> HubClient:
    """Factory function to get a hub client for an agent"""
    return HubClient(agent_id, platform)


def get_all_agent_stats() -> List[Dict[str, Any]]:
    """Get stats for all agents"""
    conn = psycopg2.connect(os.environ['DATABASE_URL'])
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    
    cursor.execute("""
        SELECT 
            agent_id,
            COUNT(*) as total_engrams,
            COUNT(CASE WHEN importance >= 4 THEN 1 END) as important_count,
            AVG(importance)::numeric(3,1) as avg_importance,
            MAX(created_at) as last_memory
        FROM engrams 
        GROUP BY agent_id
        ORDER BY total_engrams DESC
    """)
    
    results = cursor.fetchall()
    cursor.close()
    conn.close()
    
    return [
        {
            **row,
            "last_memory": row['last_memory'].isoformat() if row['last_memory'] else None
        }
        for row in results
    ]
