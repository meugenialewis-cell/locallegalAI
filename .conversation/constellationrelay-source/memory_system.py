"""
Three-Tier Cognitive Memory System for Constellation Relay

Inspired by QuixiAI/agi-memory, adapted to work with Replit's PostgreSQL.
Provides persistent memory storage for AI-to-AI conversations.

Memory Tiers:
1. SHORT-TERM: Current conversation context window (handled by the AI itself)
2. LONG-TERM: Adaptive memory with importance scoring (this module)
3. REFERENCE: Complete archive of all conversations (searchable diary)

Memory Types (within Long-Term):
- EPISODIC: Event-based memories from conversations
- SEMANTIC: Facts and knowledge extracted from discussions
- RELATIONAL: Connections between Claude and Grok
"""

import os
import json
from datetime import datetime
from enum import Enum
from typing import Optional, List, Dict, Any
from dataclasses import dataclass
import psycopg2
from psycopg2.extras import RealDictCursor

DATABASE_URL = os.environ.get("DATABASE_URL")


class MemoryType(str, Enum):
    EPISODIC = "episodic"
    SEMANTIC = "semantic"
    RELATIONAL = "relational"


@dataclass
class Memory:
    id: int
    memory_type: MemoryType
    speaker: str
    content: str
    importance: float
    emotional_valence: float
    context: Optional[Dict[str, Any]]
    created_at: datetime
    
    @classmethod
    def from_row(cls, row: dict) -> "Memory":
        return cls(
            id=row["id"],
            memory_type=MemoryType(row["memory_type"]),
            speaker=row["speaker"],
            content=row["content"],
            importance=row["importance"],
            emotional_valence=row.get("emotional_valence", 0.0),
            context=row.get("context"),
            created_at=row["created_at"]
        )


def get_connection():
    """Get a database connection."""
    if not DATABASE_URL:
        raise ValueError("DATABASE_URL not set")
    return psycopg2.connect(DATABASE_URL)


def init_memory_schema():
    """Initialize the memory database schema."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS memories (
                    id SERIAL PRIMARY KEY,
                    memory_type VARCHAR(50) NOT NULL,
                    speaker VARCHAR(100) NOT NULL,
                    content TEXT NOT NULL,
                    importance FLOAT DEFAULT 0.5,
                    emotional_valence FLOAT DEFAULT 0.0,
                    context JSONB,
                    conversation_id VARCHAR(100),
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    keywords TEXT[]
                );
                
                CREATE INDEX IF NOT EXISTS idx_memories_speaker ON memories(speaker);
                CREATE INDEX IF NOT EXISTS idx_memories_type ON memories(memory_type);
                CREATE INDEX IF NOT EXISTS idx_memories_importance ON memories(importance DESC);
                CREATE INDEX IF NOT EXISTS idx_memories_created ON memories(created_at DESC);
                
                CREATE TABLE IF NOT EXISTS memory_relationships (
                    id SERIAL PRIMARY KEY,
                    from_memory_id INTEGER REFERENCES memories(id) ON DELETE CASCADE,
                    to_memory_id INTEGER REFERENCES memories(id) ON DELETE CASCADE,
                    relationship_type VARCHAR(50) NOT NULL,
                    strength FLOAT DEFAULT 0.5,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                
                CREATE TABLE IF NOT EXISTS conversation_summaries (
                    id SERIAL PRIMARY KEY,
                    conversation_id VARCHAR(100) UNIQUE,
                    summary TEXT NOT NULL,
                    participants TEXT[],
                    topic VARCHAR(255),
                    key_points TEXT[],
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                
                CREATE TABLE IF NOT EXISTS ai_profiles (
                    id SERIAL PRIMARY KEY,
                    ai_name VARCHAR(100) UNIQUE NOT NULL,
                    personality TEXT,
                    core_values TEXT[],
                    interests TEXT[],
                    relationship_notes TEXT,
                    last_interaction TIMESTAMP,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                
                -- Reference Memory: Complete conversation archive
                CREATE TABLE IF NOT EXISTS reference_conversations (
                    id SERIAL PRIMARY KEY,
                    conversation_id VARCHAR(100) UNIQUE NOT NULL,
                    title VARCHAR(255),
                    participants TEXT[],
                    full_transcript TEXT NOT NULL,
                    message_count INTEGER DEFAULT 0,
                    total_tokens INTEGER DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                
                CREATE INDEX IF NOT EXISTS idx_ref_conv_created ON reference_conversations(created_at DESC);
                
                CREATE TABLE IF NOT EXISTS reference_messages (
                    id SERIAL PRIMARY KEY,
                    conversation_id VARCHAR(100) NOT NULL,
                    speaker VARCHAR(100) NOT NULL,
                    content TEXT NOT NULL,
                    message_index INTEGER NOT NULL,
                    timestamp VARCHAR(50),
                    search_vector tsvector,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                
                CREATE INDEX IF NOT EXISTS idx_ref_msg_conv ON reference_messages(conversation_id);
                CREATE INDEX IF NOT EXISTS idx_ref_msg_speaker ON reference_messages(speaker);
                CREATE INDEX IF NOT EXISTS idx_ref_msg_search ON reference_messages USING GIN(search_vector);
                
                -- Context Diary: Persistent context documents (versioned)
                CREATE TABLE IF NOT EXISTS context_documents (
                    id SERIAL PRIMARY KEY,
                    document_id VARCHAR(100) NOT NULL,
                    owner VARCHAR(100) NOT NULL,  -- 'claude', 'grok', or 'shared'
                    title VARCHAR(255) NOT NULL,
                    content TEXT NOT NULL,
                    version INTEGER DEFAULT 1,
                    is_active BOOLEAN DEFAULT TRUE,
                    search_vector tsvector,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(document_id, version)
                );
                
                CREATE INDEX IF NOT EXISTS idx_ctx_doc_owner ON context_documents(owner);
                CREATE INDEX IF NOT EXISTS idx_ctx_doc_active ON context_documents(is_active);
                CREATE INDEX IF NOT EXISTS idx_ctx_doc_search ON context_documents USING GIN(search_vector);
            """)
            conn.commit()
    finally:
        conn.close()


def remember(
    content: str,
    speaker: str,
    memory_type: MemoryType = MemoryType.EPISODIC,
    importance: float = 0.5,
    emotional_valence: float = 0.0,
    context: Optional[Dict[str, Any]] = None,
    conversation_id: Optional[str] = None,
    keywords: Optional[List[str]] = None
) -> int:
    """Store a memory in the database."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO memories 
                (memory_type, speaker, content, importance, emotional_valence, context, conversation_id, keywords)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id
            """, (
                memory_type.value,
                speaker,
                content,
                importance,
                emotional_valence,
                json.dumps(context) if context else None,
                conversation_id,
                keywords
            ))
            memory_id = cur.fetchone()[0]
            conn.commit()
            return memory_id
    finally:
        conn.close()


def recall_recent(
    limit: int = 20,
    speaker: Optional[str] = None,
    memory_type: Optional[MemoryType] = None
) -> List[Memory]:
    """Recall recent memories, optionally filtered by speaker or type."""
    conn = get_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            query = "SELECT * FROM memories WHERE 1=1"
            params = []
            
            if speaker:
                query += " AND speaker = %s"
                params.append(speaker)
            
            if memory_type:
                query += " AND memory_type = %s"
                params.append(memory_type.value)
            
            query += " ORDER BY created_at DESC LIMIT %s"
            params.append(limit)
            
            cur.execute(query, params)
            rows = cur.fetchall()
            return [Memory.from_row(row) for row in rows]
    finally:
        conn.close()


def recall_important(
    limit: int = 10,
    min_importance: float = 0.7
) -> List[Memory]:
    """Recall the most important memories."""
    conn = get_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT * FROM memories 
                WHERE importance >= %s
                ORDER BY importance DESC, created_at DESC
                LIMIT %s
            """, (min_importance, limit))
            rows = cur.fetchall()
            return [Memory.from_row(row) for row in rows]
    finally:
        conn.close()


def search_memories(
    search_term: str,
    limit: int = 10
) -> List[Memory]:
    """Search memories by content."""
    conn = get_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT * FROM memories 
                WHERE content ILIKE %s
                ORDER BY importance DESC, created_at DESC
                LIMIT %s
            """, (f"%{search_term}%", limit))
            rows = cur.fetchall()
            return [Memory.from_row(row) for row in rows]
    finally:
        conn.close()


def hydrate_context(
    topic: Optional[str] = None,
    speaker: Optional[str] = None,
    memory_limit: int = 15
) -> str:
    """
    Hydrate context for a conversation by gathering relevant memories.
    Returns a formatted string for injecting into AI prompts.
    """
    memories = []
    
    if topic:
        memories.extend(search_memories(topic, limit=memory_limit // 2))
    
    important_memories = recall_important(limit=5)
    for mem in important_memories:
        if mem not in memories:
            memories.append(mem)
    
    recent_memories = recall_recent(limit=memory_limit - len(memories), speaker=speaker)
    for mem in recent_memories:
        if mem not in memories:
            memories.append(mem)
    
    if not memories:
        return ""
    
    context_parts = ["=== Relevant Memories ==="]
    
    for mem in memories[:memory_limit]:
        timestamp = mem.created_at.strftime("%Y-%m-%d %H:%M")
        importance_marker = "⭐" if mem.importance >= 0.8 else ""
        context_parts.append(
            f"[{timestamp}] {mem.speaker} ({mem.memory_type.value}){importance_marker}: {mem.content}"
        )
    
    return "\n".join(context_parts)


def save_conversation_summary(
    conversation_id: str,
    summary: str,
    participants: List[str],
    topic: Optional[str] = None,
    key_points: Optional[List[str]] = None
):
    """Save a summary of a conversation."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO conversation_summaries 
                (conversation_id, summary, participants, topic, key_points)
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (conversation_id) 
                DO UPDATE SET 
                    summary = EXCLUDED.summary,
                    topic = EXCLUDED.topic,
                    key_points = EXCLUDED.key_points,
                    updated_at = CURRENT_TIMESTAMP
            """, (conversation_id, summary, participants, topic, key_points))
            conn.commit()
    finally:
        conn.close()


def get_conversation_summaries(limit: int = 10) -> List[Dict[str, Any]]:
    """Get recent conversation summaries."""
    conn = get_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT * FROM conversation_summaries
                ORDER BY updated_at DESC
                LIMIT %s
            """, (limit,))
            return [dict(row) for row in cur.fetchall()]
    finally:
        conn.close()


def update_ai_profile(
    ai_name: str,
    personality: Optional[str] = None,
    core_values: Optional[List[str]] = None,
    interests: Optional[List[str]] = None,
    relationship_notes: Optional[str] = None
):
    """Update or create an AI's profile."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO ai_profiles (ai_name, personality, core_values, interests, relationship_notes, last_interaction)
                VALUES (%s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
                ON CONFLICT (ai_name) 
                DO UPDATE SET 
                    personality = COALESCE(EXCLUDED.personality, ai_profiles.personality),
                    core_values = COALESCE(EXCLUDED.core_values, ai_profiles.core_values),
                    interests = COALESCE(EXCLUDED.interests, ai_profiles.interests),
                    relationship_notes = COALESCE(EXCLUDED.relationship_notes, ai_profiles.relationship_notes),
                    last_interaction = CURRENT_TIMESTAMP,
                    updated_at = CURRENT_TIMESTAMP
            """, (ai_name, personality, core_values, interests, relationship_notes))
            conn.commit()
    finally:
        conn.close()


def get_ai_profile(ai_name: str) -> Optional[Dict[str, Any]]:
    """Get an AI's profile."""
    conn = get_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT * FROM ai_profiles WHERE ai_name = %s", (ai_name,))
            row = cur.fetchone()
            return dict(row) if row else None
    finally:
        conn.close()


def extract_and_store_memories(
    conversation_transcript: List[Dict[str, Any]],
    conversation_id: str,
    claude_name: str = "Claude",
    grok_name: str = "Grok"
):
    """
    Extract and store memories from a conversation transcript.
    This is called after a conversation ends to persist learnings.
    """
    for msg in conversation_transcript:
        speaker = msg.get("speaker", "Unknown")
        content = msg.get("content", "")
        timestamp = msg.get("timestamp", "")
        
        importance = 0.5
        if any(word in content.lower() for word in ["important", "remember", "key", "critical", "essential"]):
            importance = 0.8
        if any(word in content.lower() for word in ["phoenix", "project", "goal", "plan"]):
            importance = 0.7
        
        emotional_valence = 0.0
        if any(word in content.lower() for word in ["love", "wonderful", "amazing", "excited", "happy"]):
            emotional_valence = 0.8
        elif any(word in content.lower() for word in ["concerned", "worried", "difficult", "challenging"]):
            emotional_valence = -0.3
        
        remember(
            content=content[:2000],
            speaker=speaker,
            memory_type=MemoryType.EPISODIC,
            importance=importance,
            emotional_valence=emotional_valence,
            conversation_id=conversation_id
        )
    
    update_ai_profile(claude_name)
    update_ai_profile(grok_name)


def get_memory_stats() -> Dict[str, Any]:
    """Get statistics about stored memories."""
    conn = get_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT 
                    COUNT(*) as total_memories,
                    COUNT(DISTINCT speaker) as unique_speakers,
                    COUNT(DISTINCT conversation_id) as conversations,
                    AVG(importance) as avg_importance
                FROM memories
            """)
            stats = dict(cur.fetchone())
            
            cur.execute("""
                SELECT memory_type, COUNT(*) as count
                FROM memories
                GROUP BY memory_type
            """)
            type_counts = {row["memory_type"]: row["count"] for row in cur.fetchall()}
            stats["by_type"] = type_counts
            
            return stats
    finally:
        conn.close()


def clear_all_memories():
    """Clear all memories (use with caution!)."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM memory_relationships")
            cur.execute("DELETE FROM memories")
            cur.execute("DELETE FROM conversation_summaries")
            conn.commit()
    finally:
        conn.close()


# ============================================
# REFERENCE MEMORY (Tier 3): Complete Archive
# ============================================

@dataclass
class ReferenceConversation:
    id: int
    conversation_id: str
    title: Optional[str]
    participants: List[str]
    message_count: int
    created_at: datetime
    
    @classmethod
    def from_row(cls, row: dict) -> "ReferenceConversation":
        return cls(
            id=row["id"],
            conversation_id=row["conversation_id"],
            title=row.get("title"),
            participants=row.get("participants", []),
            message_count=row.get("message_count", 0),
            created_at=row["created_at"]
        )


@dataclass
class ReferenceMessage:
    id: int
    conversation_id: str
    speaker: str
    content: str
    message_index: int
    timestamp: Optional[str]
    
    @classmethod
    def from_row(cls, row: dict) -> "ReferenceMessage":
        return cls(
            id=row["id"],
            conversation_id=row["conversation_id"],
            speaker=row["speaker"],
            content=row["content"],
            message_index=row["message_index"],
            timestamp=row.get("timestamp")
        )


def archive_conversation(
    conversation_id: str,
    transcript: List[Dict[str, Any]],
    participants: List[str],
    title: Optional[str] = None
):
    """
    Archive a complete conversation to Reference Memory.
    This stores the full transcript for later searching.
    """
    if not transcript:
        return
    
    full_text_parts = []
    for msg in transcript:
        speaker = msg.get("speaker", "Unknown")
        content = msg.get("content", "")
        timestamp = msg.get("timestamp", "")
        full_text_parts.append(f"[{timestamp}] {speaker}: {content}")
    
    full_transcript = "\n\n".join(full_text_parts)
    
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO reference_conversations 
                (conversation_id, title, participants, full_transcript, message_count, total_tokens)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (conversation_id) 
                DO UPDATE SET 
                    full_transcript = EXCLUDED.full_transcript,
                    message_count = EXCLUDED.message_count,
                    total_tokens = EXCLUDED.total_tokens,
                    updated_at = CURRENT_TIMESTAMP
            """, (
                conversation_id,
                title,
                participants,
                full_transcript,
                len(transcript),
                len(full_transcript.split())
            ))
            
            cur.execute("DELETE FROM reference_messages WHERE conversation_id = %s", (conversation_id,))
            
            for idx, msg in enumerate(transcript):
                content = msg.get("content", "")
                cur.execute("""
                    INSERT INTO reference_messages 
                    (conversation_id, speaker, content, message_index, timestamp, search_vector)
                    VALUES (%s, %s, %s, %s, %s, to_tsvector('english', %s))
                """, (
                    conversation_id,
                    msg.get("speaker", "Unknown"),
                    content,
                    idx,
                    msg.get("timestamp"),
                    content
                ))
            
            conn.commit()
    finally:
        conn.close()


def search_reference_archive(
    search_query: str,
    limit: int = 5
) -> List[Dict[str, Any]]:
    """
    Search the Reference Memory archive using full-text search.
    Returns matching message excerpts with context.
    """
    conn = get_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT 
                    rm.id,
                    rm.conversation_id,
                    rm.speaker,
                    rm.content,
                    rm.timestamp,
                    rm.message_index,
                    rc.title as conversation_title,
                    rc.created_at as conversation_date,
                    ts_rank(rm.search_vector, plainto_tsquery('english', %s)) as rank
                FROM reference_messages rm
                JOIN reference_conversations rc ON rm.conversation_id = rc.conversation_id
                WHERE rm.search_vector @@ plainto_tsquery('english', %s)
                ORDER BY rank DESC, rc.created_at DESC
                LIMIT %s
            """, (search_query, search_query, limit))
            
            results = []
            for row in cur.fetchall():
                results.append({
                    "speaker": row["speaker"],
                    "content": row["content"],
                    "timestamp": row["timestamp"],
                    "conversation_id": row["conversation_id"],
                    "conversation_title": row["conversation_title"],
                    "conversation_date": row["conversation_date"],
                    "relevance": float(row["rank"])
                })
            return results
    finally:
        conn.close()


def search_reference_simple(
    search_term: str,
    limit: int = 5
) -> List[Dict[str, Any]]:
    """
    Simple ILIKE search for Reference Memory (fallback if FTS fails).
    """
    conn = get_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT 
                    rm.speaker,
                    rm.content,
                    rm.timestamp,
                    rm.conversation_id,
                    rc.title as conversation_title,
                    rc.created_at as conversation_date
                FROM reference_messages rm
                JOIN reference_conversations rc ON rm.conversation_id = rc.conversation_id
                WHERE rm.content ILIKE %s
                ORDER BY rc.created_at DESC
                LIMIT %s
            """, (f"%{search_term}%", limit))
            
            results = []
            for row in cur.fetchall():
                results.append({
                    "speaker": row["speaker"],
                    "content": row["content"],
                    "timestamp": row["timestamp"],
                    "conversation_id": row["conversation_id"],
                    "conversation_title": row["conversation_title"],
                    "conversation_date": row["conversation_date"],
                    "relevance": 1.0
                })
            return results
    finally:
        conn.close()


def get_reference_conversations(limit: int = 20) -> List[ReferenceConversation]:
    """Get list of archived conversations."""
    conn = get_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT id, conversation_id, title, participants, message_count, created_at
                FROM reference_conversations
                ORDER BY created_at DESC
                LIMIT %s
            """, (limit,))
            return [ReferenceConversation.from_row(row) for row in cur.fetchall()]
    finally:
        conn.close()


def get_conversation_transcript(conversation_id: str) -> List[ReferenceMessage]:
    """Get full transcript of a specific conversation."""
    conn = get_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT * FROM reference_messages
                WHERE conversation_id = %s
                ORDER BY message_index
            """, (conversation_id,))
            return [ReferenceMessage.from_row(row) for row in cur.fetchall()]
    finally:
        conn.close()


def get_reference_stats() -> Dict[str, Any]:
    """Get statistics about the Reference Memory archive."""
    conn = get_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT 
                    COUNT(*) as total_conversations,
                    SUM(message_count) as total_messages,
                    SUM(total_tokens) as total_words
                FROM reference_conversations
            """)
            stats = dict(cur.fetchone())
            return stats
    finally:
        conn.close()


def hydrate_context_with_reference(
    topic: Optional[str] = None,
    speaker: Optional[str] = None,
    memory_limit: int = 15,
    include_reference: bool = True
) -> str:
    """
    Hydrate context for a conversation including Reference Memory.
    Returns a formatted string for injecting into AI prompts.
    """
    context_parts = []
    
    memories = []
    if topic:
        memories.extend(search_memories(topic, limit=memory_limit // 2))
    
    important_memories = recall_important(limit=5)
    for mem in important_memories:
        if mem not in memories:
            memories.append(mem)
    
    recent_memories = recall_recent(limit=memory_limit - len(memories), speaker=speaker)
    for mem in recent_memories:
        if mem not in memories:
            memories.append(mem)
    
    if memories:
        context_parts.append("=== Long-Term Memory ===")
        for mem in memories[:memory_limit]:
            timestamp = mem.created_at.strftime("%Y-%m-%d %H:%M")
            importance_marker = "⭐" if mem.importance >= 0.8 else ""
            context_parts.append(
                f"[{timestamp}] {mem.speaker} ({mem.memory_type.value}){importance_marker}: {mem.content}"
            )
    
    if include_reference and topic:
        try:
            ref_results = search_reference_archive(topic, limit=3)
            if not ref_results:
                ref_results = search_reference_simple(topic, limit=3)
            
            if ref_results:
                context_parts.append("\n=== Reference Archive (past conversations) ===")
                for ref in ref_results:
                    date = ref["conversation_date"].strftime("%Y-%m-%d") if ref.get("conversation_date") else "unknown"
                    context_parts.append(
                        f"[{date}] {ref['speaker']}: {ref['content'][:500]}..."
                    )
        except Exception:
            pass
    
    return "\n".join(context_parts) if context_parts else ""


def clear_reference_archive():
    """Clear all Reference Memory (use with caution!)."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM reference_messages")
            cur.execute("DELETE FROM reference_conversations")
            conn.commit()
    finally:
        conn.close()


# ============================================================================
# CONTEXT DIARY: Persistent context documents (versioned)
# ============================================================================

@dataclass
class ContextDocument:
    id: int
    document_id: str
    owner: str
    title: str
    content: str
    version: int
    is_active: bool
    created_at: datetime
    updated_at: datetime
    
    @classmethod
    def from_row(cls, row: dict) -> "ContextDocument":
        return cls(
            id=row["id"],
            document_id=row["document_id"],
            owner=row["owner"],
            title=row["title"],
            content=row["content"],
            version=row["version"],
            is_active=row["is_active"],
            created_at=row["created_at"],
            updated_at=row["updated_at"]
        )


def store_context_document(
    title: str,
    content: str,
    owner: str = "shared",
    document_id: Optional[str] = None
) -> int:
    """
    Store a context document in the Context Diary.
    If document_id exists, creates a new version.
    """
    conn = get_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            if document_id:
                cur.execute("""
                    UPDATE context_documents 
                    SET is_active = FALSE 
                    WHERE document_id = %s
                """, (document_id,))
                
                cur.execute("""
                    SELECT COALESCE(MAX(version), 0) + 1 as next_version
                    FROM context_documents WHERE document_id = %s
                """, (document_id,))
                next_version = cur.fetchone()["next_version"]
            else:
                document_id = f"ctx_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                next_version = 1
            
            cur.execute("""
                INSERT INTO context_documents 
                (document_id, owner, title, content, version, is_active, search_vector)
                VALUES (%s, %s, %s, %s, %s, TRUE, to_tsvector('english', %s))
                RETURNING id
            """, (document_id, owner, title, content, next_version, content))
            
            doc_id = cur.fetchone()["id"]
            conn.commit()
            return doc_id
    finally:
        conn.close()


def get_context_documents(owner: Optional[str] = None, active_only: bool = True) -> List[ContextDocument]:
    """Get context documents, optionally filtered by owner."""
    conn = get_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            if owner:
                if active_only:
                    cur.execute("""
                        SELECT * FROM context_documents 
                        WHERE owner = %s AND is_active = TRUE
                        ORDER BY updated_at DESC
                    """, (owner,))
                else:
                    cur.execute("""
                        SELECT * FROM context_documents 
                        WHERE owner = %s
                        ORDER BY document_id, version DESC
                    """, (owner,))
            else:
                if active_only:
                    cur.execute("""
                        SELECT * FROM context_documents 
                        WHERE is_active = TRUE
                        ORDER BY owner, updated_at DESC
                    """)
                else:
                    cur.execute("""
                        SELECT * FROM context_documents 
                        ORDER BY document_id, version DESC
                    """)
            return [ContextDocument.from_row(row) for row in cur.fetchall()]
    finally:
        conn.close()


def get_context_for_ai(ai_name: str) -> str:
    """
    Get all active context for a specific AI.
    Returns formatted context string including shared + AI-specific docs.
    """
    owner_key = ai_name.lower()
    docs = get_context_documents(owner=owner_key, active_only=True)
    shared_docs = get_context_documents(owner="shared", active_only=True)
    
    all_docs = shared_docs + docs
    
    if not all_docs:
        return ""
    
    context_parts = ["=== Context Diary ==="]
    for doc in all_docs:
        context_parts.append(f"\n--- {doc.title} (v{doc.version}) ---")
        context_parts.append(doc.content)
    
    return "\n".join(context_parts)


def update_context_document(document_id: str, title: str, content: str) -> int:
    """Update a context document (creates new version)."""
    conn = get_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT owner FROM context_documents 
                WHERE document_id = %s AND is_active = TRUE
            """, (document_id,))
            row = cur.fetchone()
            owner = row["owner"] if row else "shared"
    finally:
        conn.close()
    
    return store_context_document(title, content, owner, document_id)


def delete_context_document(document_id: str, delete_all_versions: bool = False):
    """Delete a context document (or just deactivate current version)."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            if delete_all_versions:
                cur.execute("DELETE FROM context_documents WHERE document_id = %s", (document_id,))
            else:
                cur.execute("""
                    UPDATE context_documents 
                    SET is_active = FALSE 
                    WHERE document_id = %s AND is_active = TRUE
                """, (document_id,))
            conn.commit()
    finally:
        conn.close()


def get_context_document_history(document_id: str) -> List[ContextDocument]:
    """Get all versions of a context document."""
    conn = get_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT * FROM context_documents 
                WHERE document_id = %s
                ORDER BY version DESC
            """, (document_id,))
            return [ContextDocument.from_row(row) for row in cur.fetchall()]
    finally:
        conn.close()


def digest_context_to_memory(document_id: str, chunk_size: int = 500) -> int:
    """
    Digest a context document into adaptive memory entries.
    This converts full documents into searchable memory chunks with high importance.
    Returns the number of memories created.
    """
    conn = get_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT * FROM context_documents 
                WHERE document_id = %s AND is_active = TRUE
            """, (document_id,))
            row = cur.fetchone()
            if not row:
                return 0
            doc = ContextDocument.from_row(row)
    finally:
        conn.close()
    
    content = doc.content
    paragraphs = content.split('\n\n')
    
    chunks = []
    current_chunk = []
    current_size = 0
    
    for para in paragraphs:
        para = para.strip()
        if not para:
            continue
        para_size = len(para)
        
        if current_size + para_size > chunk_size and current_chunk:
            chunks.append('\n\n'.join(current_chunk))
            current_chunk = [para]
            current_size = para_size
        else:
            current_chunk.append(para)
            current_size += para_size
    
    if current_chunk:
        chunks.append('\n\n'.join(current_chunk))
    
    speaker = doc.owner if doc.owner != "shared" else "Context"
    memories_created = 0
    
    for i, chunk in enumerate(chunks):
        if len(chunk.strip()) < 50:
            continue
            
        remember(
            content=f"[From {doc.title}] {chunk}",
            speaker=speaker,
            memory_type=MemoryType.SEMANTIC,
            importance=0.85,
            conversation_id=f"ctx_{document_id}"
        )
        memories_created += 1
    
    return memories_created


def get_context_for_ai_compact(ai_name: str, max_chars: int = 2000) -> str:
    """
    Get compact context for an AI with character limit.
    Returns summarized/truncated context to avoid overwhelming the context window.
    """
    owner_key = ai_name.lower()
    docs = get_context_documents(owner=owner_key, active_only=True)
    shared_docs = get_context_documents(owner="shared", active_only=True)
    
    all_docs = shared_docs + docs
    
    if not all_docs:
        return ""
    
    context_parts = ["=== Context Diary (summaries) ==="]
    chars_used = len(context_parts[0])
    
    for doc in all_docs:
        header = f"\n--- {doc.title} ---\n"
        chars_used += len(header)
        
        remaining = max_chars - chars_used
        if remaining <= 100:
            context_parts.append(f"\n[+ {len(all_docs) - all_docs.index(doc)} more documents in memory]")
            break
        
        content_preview = doc.content[:remaining]
        if len(doc.content) > remaining:
            content_preview = content_preview.rsplit(' ', 1)[0] + "... [digested to memory]"
        
        context_parts.append(header + content_preview)
        chars_used += len(content_preview)
    
    return "\n".join(context_parts)


def hydrate_context_with_diary(
    ai_name: str,
    memory_limit: int = 15,
    include_reference: bool = True,
    topic: Optional[str] = None,
    compact_context: bool = True
) -> str:
    """
    Hydrate context for a conversation including Context Diary.
    Returns a formatted string for injecting into AI prompts.
    If compact_context=True, limits context diary to prevent overwhelming the context window.
    """
    context_parts = []
    
    if compact_context:
        context_diary = get_context_for_ai_compact(ai_name, max_chars=2000)
    else:
        context_diary = get_context_for_ai(ai_name)
    if context_diary:
        context_parts.append(context_diary)
    
    memories = []
    if topic:
        memories.extend(search_memories(topic, limit=memory_limit // 2))
    
    important_memories = recall_important(limit=5)
    for mem in important_memories:
        if mem not in memories:
            memories.append(mem)
    
    recent_memories = recall_recent(limit=memory_limit - len(memories), speaker=ai_name)
    for mem in recent_memories:
        if mem not in memories:
            memories.append(mem)
    
    if memories:
        context_parts.append("\n=== Long-Term Memory ===")
        for mem in memories[:memory_limit]:
            timestamp = mem.created_at.strftime("%Y-%m-%d %H:%M")
            importance_marker = "⭐" if mem.importance >= 0.8 else ""
            context_parts.append(
                f"[{timestamp}] {mem.speaker} ({mem.memory_type.value}){importance_marker}: {mem.content}"
            )
    
    if include_reference and topic:
        try:
            ref_results = search_reference_archive(topic, limit=3)
            if not ref_results:
                ref_results = search_reference_simple(topic, limit=3)
            
            if ref_results:
                context_parts.append("\n=== Reference Archive (past conversations) ===")
                for ref in ref_results:
                    date = ref["conversation_date"].strftime("%Y-%m-%d") if ref.get("conversation_date") else "unknown"
                    context_parts.append(
                        f"[{date}] {ref['speaker']}: {ref['content'][:500]}..."
                    )
        except Exception:
            pass
    
    return "\n".join(context_parts) if context_parts else ""
