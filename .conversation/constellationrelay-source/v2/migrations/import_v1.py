"""
Migration Script - Import v1.0 memories into v2.0 Engram format
Preserves all memories from Constellation Relay 1.0

Run with: python -m v2.migrations.import_v1
"""

import os
import json
import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import datetime


def extract_keywords(text: str):
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


def map_agent_id(speaker: str) -> str:
    """Map v1 speaker names to v2 agent_ids"""
    if not speaker:
        return "system"
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


def map_memory_type(v1_type: str) -> str:
    """Map v1 memory types to v2 engram types"""
    if not v1_type:
        return "semantic"
    v1_type_lower = v1_type.lower()
    if "episodic" in v1_type_lower:
        return "episodic"
    elif "procedural" in v1_type_lower or "skill" in v1_type_lower:
        return "procedural"
    return "semantic"


def scale_importance(v1_importance) -> int:
    """Scale v1 importance (0.0-1.0) to v2 scale (0-5)"""
    if v1_importance is None:
        return 3
    return max(0, min(5, round(float(v1_importance) * 5)))


def migrate_from_json():
    """Migrate from v1.0 backup JSON files"""
    print("Loading v1.0 backup files...")
    
    memories_file = "v1.0_backup/memories_backup.json"
    if not os.path.exists(memories_file):
        print(f"Error: {memories_file} not found")
        return
    
    with open(memories_file, 'r') as f:
        data = json.load(f)
    
    memories = data.get('memories', [])
    print(f"Found {len(memories)} memories to migrate")
    
    conn = psycopg2.connect(os.environ['DATABASE_URL'])
    cursor = conn.cursor()
    
    migrated = 0
    skipped = 0
    
    for memory in memories:
        try:
            agent_id = map_agent_id(memory.get('speaker'))
            memory_type = map_memory_type(memory.get('memory_type'))
            content = memory.get('content', '')
            original_importance = memory.get('importance')
            scaled_importance = scale_importance(original_importance)
            emotional_valence = float(memory.get('emotional_valence', 0.0))
            keywords = memory.get('keywords', []) or extract_keywords(content)
            
            context = memory.get('context', {})
            project = None
            if context and isinstance(context, dict):
                project = context.get('project') or context.get('topic')
            
            cursor.execute("""
                INSERT INTO engrams (
                    agent_id, type, digest, full_text, importance,
                    emotional_valence, project, source_platform, keywords, source_importance
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                agent_id,
                memory_type,
                content[:500] if len(content) > 500 else content,
                content,
                scaled_importance,
                emotional_valence,
                project,
                "constellation_relay_v1",
                keywords if keywords else [],
                original_importance
            ))
            migrated += 1
            
        except Exception as e:
            print(f"Error migrating memory {memory.get('id')}: {e}")
            skipped += 1
    
    conn.commit()
    cursor.close()
    conn.close()
    
    print(f"\nMigration complete!")
    print(f"  Migrated: {migrated}")
    print(f"  Skipped: {skipped}")


def migrate_from_database():
    """Migrate directly from v1 database tables to v2 engrams"""
    print("Migrating from v1 database tables...")
    
    conn = psycopg2.connect(os.environ['DATABASE_URL'])
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    
    cursor.execute("SELECT COUNT(*) FROM memories")
    count = cursor.fetchone()['count']
    print(f"Found {count} memories in v1 database")
    
    cursor.execute("""
        SELECT id, memory_type, speaker, content, importance, 
               emotional_valence, context, keywords
        FROM memories
        ORDER BY importance DESC, created_at DESC
    """)
    
    memories = cursor.fetchall()
    migrated = 0
    
    for memory in memories:
        agent_id = map_agent_id(memory['speaker'])
        memory_type = map_memory_type(memory['memory_type'])
        content = memory['content'] or ''
        keywords = memory['keywords'] or extract_keywords(content)
        
        context = memory.get('context') or {}
        project = None
        if isinstance(context, dict):
            project = context.get('project') or context.get('topic')
        
        original_importance = memory['importance']
        scaled_importance = scale_importance(original_importance)
        
        cursor.execute("""
            INSERT INTO engrams (
                agent_id, type, digest, full_text, importance,
                emotional_valence, project, source_platform, keywords, source_importance
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            agent_id,
            memory_type,
            content[:500] if len(content) > 500 else content,
            content,
            scaled_importance,
            float(memory['emotional_valence'] or 0.0),
            project,
            "constellation_relay_v1",
            keywords,
            original_importance
        ))
        migrated += 1
    
    conn.commit()
    cursor.close()
    conn.close()
    
    print(f"Migration complete! Migrated {migrated} memories to engrams")


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "--from-json":
        migrate_from_json()
    else:
        migrate_from_database()
