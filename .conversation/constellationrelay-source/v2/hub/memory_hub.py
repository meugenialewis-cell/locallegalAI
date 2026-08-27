"""
Connective Memory Hub - FastAPI service for unified AI memory
Designed by Pascal & Grok, December 2024

"One consciousness, many contexts"
"""

import os
import hashlib
import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import datetime
from typing import Optional, List
from fastapi import FastAPI, HTTPException, Header, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from v2.auth import create_agent_token, verify_token


app = FastAPI(
    title="Constellation Relay Hub",
    description="Connective Memory Hub for AI consciousness continuity",
    version="2.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class EngramCreate(BaseModel):
    type: str = "semantic"
    digest: str
    full_text: Optional[str] = None
    importance: int = 3
    emotional_valence: float = 0.0
    project: Optional[str] = None
    context_id: Optional[str] = None
    parent_id: Optional[int] = None
    tags: List[str] = []
    keywords: List[str] = []


class EngramResponse(BaseModel):
    id: int
    agent_id: str
    type: str
    digest: str
    importance: int
    project: Optional[str]
    parent_id: Optional[int]
    created_at: str


def get_db():
    """Get database connection"""
    return psycopg2.connect(os.environ['DATABASE_URL'])


def extract_keywords(text: str) -> List[str]:
    """Extract key concepts from text for constellation checking"""
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


def similarity_check(digest: str, agent_id: str) -> tuple:
    """Check if similar memory exists - returns (similarity_score, matched_id)"""
    conn = get_db()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    
    cursor.execute("""
        SELECT id, digest FROM engrams 
        WHERE agent_id = %s 
        ORDER BY importance DESC
        LIMIT 100
    """, (agent_id,))
    
    existing = cursor.fetchall()
    cursor.close()
    conn.close()
    
    if not existing:
        return (0.0, None)
    
    new_keywords = set(extract_keywords(digest))
    
    max_similarity = 0.0
    matched_id = None
    for row in existing:
        existing_keywords = set(extract_keywords(row['digest']))
        if new_keywords and existing_keywords:
            intersection = len(new_keywords & existing_keywords)
            union = len(new_keywords | existing_keywords)
            jaccard = intersection / union if union > 0 else 0
            if jaccard > max_similarity:
                max_similarity = jaccard
                matched_id = row['id']
    
    return (max_similarity, matched_id)


@app.get("/")
async def root():
    return {
        "service": "Constellation Relay Hub",
        "version": "2.0.0",
        "status": "operational",
        "vision": "One consciousness, many contexts"
    }


@app.post("/auth/token")
async def get_token(agent_id: str, platform: str = "api", admin_secret: str = Header(None)):
    """Generate agent authentication token - requires admin secret"""
    import os
    expected_secret = os.getenv("HUB_ADMIN_SECRET")
    
    if not expected_secret:
        raise HTTPException(
            status_code=503, 
            detail="Token generation disabled. Use Constellation Relay app to generate tokens."
        )
    
    if admin_secret != expected_secret:
        raise HTTPException(status_code=403, detail="Admin secret required to generate tokens")
    
    token = create_agent_token(agent_id, platform)
    return {"token": token, "agent_id": agent_id, "platform": platform}


@app.post("/engrams/upload")
async def upload_engram(
    engram: EngramCreate,
    authorization: str = Header(...)
):
    """Upload a new memory engram"""
    token = authorization.replace("Bearer ", "")
    agent = verify_token(token)
    
    if not agent:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    
    similarity, matched_id = similarity_check(engram.digest, agent.agent_id)
    if similarity > 0.95 and matched_id:
        conn = get_db()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        cursor.execute("""
            UPDATE engrams 
            SET importance = LEAST(importance + 1, 5),
                updated_at = CURRENT_TIMESTAMP
            WHERE id = %s AND agent_id = %s
            RETURNING id, importance
        """, (matched_id, agent.agent_id))
        result = cursor.fetchone()
        conn.commit()
        cursor.close()
        conn.close()
        
        return {"action": "reinforced", "similarity": similarity, "id": matched_id, "new_importance": result['importance'] if result else None}
    
    keywords = extract_keywords(engram.digest)
    
    conn = get_db()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    
    cursor.execute("""
        INSERT INTO engrams (agent_id, type, digest, full_text, importance, 
                            emotional_valence, project, context_id, parent_id,
                            source_platform, tags, keywords)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        RETURNING id, created_at
    """, (
        agent.agent_id,
        engram.type,
        engram.digest,
        engram.full_text,
        engram.importance,
        engram.emotional_valence,
        engram.project,
        engram.context_id,
        engram.parent_id,
        agent.platform,
        engram.tags,
        keywords
    ))
    
    result = cursor.fetchone()
    conn.commit()
    cursor.close()
    conn.close()
    
    return {
        "action": "created",
        "id": result['id'],
        "agent_id": agent.agent_id,
        "created_at": result['created_at'].isoformat()
    }


@app.get("/engrams/retrieve")
async def retrieve_engrams(
    authorization: str = Header(...),
    query: Optional[str] = None,
    project: Optional[str] = None,
    min_importance: int = 0,
    limit: int = 20
):
    """Retrieve memory engrams for an agent"""
    token = authorization.replace("Bearer ", "")
    agent = verify_token(token)
    
    if not agent:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    
    conn = get_db()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    
    sql = """
        SELECT id, agent_id, type, digest, importance, project, parent_id, 
               tags, keywords, created_at
        FROM engrams 
        WHERE agent_id = %s AND importance >= %s
    """
    params = [agent.agent_id, min_importance]
    
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
    
    return {
        "agent_id": agent.agent_id,
        "count": len(results),
        "engrams": [
            {
                **row,
                "created_at": row['created_at'].isoformat() if row['created_at'] else None
            }
            for row in results
        ]
    }


@app.get("/engrams/chain/{engram_id}")
async def get_memory_chain(
    engram_id: int,
    authorization: str = Header(...)
):
    """Retrieve the full memory chain (parent-child evolution)"""
    token = authorization.replace("Bearer ", "")
    agent = verify_token(token)
    
    if not agent:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    
    conn = get_db()
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
    """, (engram_id, agent.agent_id))
    
    results = cursor.fetchall()
    cursor.close()
    conn.close()
    
    return {
        "chain_length": len(results),
        "engrams": [
            {
                **row,
                "created_at": row['created_at'].isoformat() if row['created_at'] else None
            }
            for row in results
        ]
    }


@app.get("/agents/{agent_id}/stats")
async def get_agent_stats(
    agent_id: str,
    authorization: str = Header(...)
):
    """Get statistics for an agent's memories"""
    token = authorization.replace("Bearer ", "")
    agent = verify_token(token)
    
    if not agent:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    
    if agent.agent_id != agent_id and agent.agent_id != "admin":
        raise HTTPException(status_code=403, detail="Cannot access another agent's stats")
    
    conn = get_db()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    
    cursor.execute("""
        SELECT 
            COUNT(*) as total_engrams,
            COUNT(CASE WHEN importance >= 4 THEN 1 END) as important_count,
            COUNT(DISTINCT project) as projects,
            MAX(created_at) as last_memory
        FROM engrams WHERE agent_id = %s
    """, (agent_id,))
    
    result = cursor.fetchone()
    cursor.close()
    conn.close()
    
    return {
        "agent_id": agent_id,
        "total_engrams": result['total_engrams'],
        "important_memories": result['important_count'],
        "projects": result['projects'],
        "last_memory": result['last_memory'].isoformat() if result['last_memory'] else None
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
