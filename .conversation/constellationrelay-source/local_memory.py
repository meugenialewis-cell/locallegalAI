"""Local Memory — the Relay's memory engine, adapted from Project Phoenix.

Ported from Phoenix's MemoryBridge (designed by Claude, January 2026) into the
Constellation Relay, July 2026. Runs entirely on SQLite — one file, no server,
no setup — so memory works on any computer and travels when the folder moves.

The philosophy is Gena's lunch-with-a-friend model: don't load everything,
load what's relevant. hydrate_context() blends a few important memories, a few
recent ones, and the most relevant archived conversations, capped in size.

Everything lives under the project folder:
    relay_memory.db   - memories (engrams) + archived conversations
    backups/          - "Back up everything" zip files
"""

import os
import re
import json
import sqlite3
import hashlib
import zipfile
from datetime import datetime
from typing import Optional, List, Dict, Any

PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(PROJECT_DIR, "relay_memory.db")
BACKUP_DIR = os.path.join(PROJECT_DIR, "backups")


class LocalMemory:
    """SQLite-backed memory: engrams + a searchable conversation archive."""

    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path
        self._init_db()

    def _connect(self):
        return sqlite3.connect(self.db_path)

    def _init_db(self):
        conn = self._connect()
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS engrams (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                agent_id TEXT NOT NULL,
                type TEXT NOT NULL DEFAULT 'episodic',
                digest TEXT NOT NULL,
                importance INTEGER DEFAULT 3,
                project TEXT,
                tags TEXT,
                created_at TEXT NOT NULL,
                content_hash TEXT UNIQUE
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS reference_conversations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                conversation_id TEXT UNIQUE NOT NULL,
                title TEXT,
                participants TEXT,
                summary TEXT,
                full_transcript TEXT NOT NULL,
                message_count INTEGER DEFAULT 0,
                created_at TEXT NOT NULL
            )
        """)
        conn.commit()
        conn.close()

    # ---------- store ----------

    def remember(
        self,
        digest: str,
        agent_id: str = "shared",
        memory_type: str = "episodic",
        importance: int = 3,
        project: Optional[str] = None,
        tags: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        digest = (digest or "").strip()
        if not digest:
            return {"status": "error", "message": "empty memory"}
        content_hash = hashlib.sha256(f"{agent_id}:{digest}".encode()).hexdigest()[:32]
        conn = self._connect()
        try:
            conn.execute(
                """INSERT INTO engrams (agent_id, type, digest, importance, project, tags, created_at, content_hash)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (agent_id.lower(), memory_type, digest, int(importance), project,
                 json.dumps(tags or []), datetime.now().isoformat(), content_hash),
            )
            conn.commit()
            return {"status": "saved", "agent": agent_id}
        except sqlite3.IntegrityError:
            return {"status": "duplicate", "agent": agent_id}
        finally:
            conn.close()

    # ---------- recall ----------

    def recall(
        self,
        query: Optional[str] = None,
        agent_id: Optional[str] = None,
        min_importance: int = 0,
        limit: int = 20,
    ) -> List[Dict[str, Any]]:
        conn = self._connect()
        sql = "SELECT agent_id, type, digest, importance, project, created_at FROM engrams WHERE importance >= ?"
        params: list = [min_importance]
        if agent_id:
            sql += " AND (agent_id = ? OR agent_id = 'shared')"
            params.append(agent_id.lower())
        if query:
            # match any word of the query, not the exact phrase
            words = [w for w in re.findall(r"\w{3,}", query.lower())][:8]
            if words:
                sql += " AND (" + " OR ".join(["LOWER(digest) LIKE ?"] * len(words)) + ")"
                params.extend(f"%{w}%" for w in words)
        sql += " ORDER BY importance DESC, created_at DESC LIMIT ?"
        params.append(limit)
        rows = conn.execute(sql, params).fetchall()
        conn.close()
        return [
            {"agent_id": r[0], "type": r[1], "digest": r[2], "importance": r[3],
             "project": r[4], "created_at": r[5]}
            for r in rows
        ]

    def hydrate_context(
        self,
        agent_id: str,
        query: Optional[str] = None,
        memory_limit: int = 8,
        reference_limit: int = 2,
        max_chars: int = 3500,
    ) -> str:
        """Blend important, recent, and relevant memories into a compact context block.

        This is the lunch-with-a-friend function: only what belongs at this table.
        """
        parts = []
        seen = set()

        important = self.recall(query=query, agent_id=agent_id, min_importance=4, limit=memory_limit)
        if important:
            parts.append("## Memories that matter")
            for m in important:
                seen.add(m["digest"][:60])
                parts.append(f"- [{m['created_at'][:10]}] {m['digest'][:600]}")

        recent = self.recall(agent_id=agent_id, min_importance=2, limit=memory_limit)
        recent_unique = [m for m in recent if m["digest"][:60] not in seen][: max(2, memory_limit // 2)]
        if recent_unique:
            parts.append("\n## Recent memories")
            for m in recent_unique:
                parts.append(f"- [{m['created_at'][:10]}] {m['digest'][:600]}")

        if query:
            refs = self.search_reference(query, limit=reference_limit)
            if refs:
                parts.append("\n## Past conversations that seem relevant")
                for ref in refs:
                    parts.append(
                        f"- [{ref['created_at'][:10]}] {ref['title'] or 'Untitled'}: "
                        f"{(ref['summary'] or ref['preview'])[:200]}"
                    )

        context = "\n".join(parts)
        if len(context) > max_chars:
            context = context[:max_chars] + "\n... [truncated]"
        return context

    # ---------- conversation archive ----------

    def archive_conversation(
        self,
        conversation_id: str,
        transcript_text: str,
        participants: List[str],
        title: str = "",
        summary: str = "",
        message_count: int = 0,
    ) -> Dict[str, Any]:
        conn = self._connect()
        try:
            conn.execute(
                """INSERT OR REPLACE INTO reference_conversations
                   (conversation_id, title, participants, summary, full_transcript, message_count, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (conversation_id, title, json.dumps(participants), summary,
                 transcript_text, message_count, datetime.now().isoformat()),
            )
            conn.commit()
            return {"status": "archived", "conversation_id": conversation_id}
        finally:
            conn.close()

    def search_reference(self, query: str, limit: int = 3) -> List[Dict[str, Any]]:
        words = [w for w in re.findall(r"\w{3,}", (query or "").lower())][:8]
        if not words:
            return []
        conn = self._connect()
        sql = (
            "SELECT conversation_id, title, summary, full_transcript, created_at FROM reference_conversations WHERE "
            + " OR ".join(["LOWER(title || ' ' || COALESCE(summary,'') || ' ' || full_transcript) LIKE ?"] * len(words))
            + " ORDER BY created_at DESC LIMIT ?"
        )
        rows = conn.execute(sql, [f"%{w}%" for w in words] + [limit]).fetchall()
        conn.close()
        results = []
        for r in rows:
            transcript = r[3] or ""
            # pull a small excerpt around the first matching word
            idx = min((transcript.lower().find(w) for w in words if transcript.lower().find(w) >= 0), default=0)
            excerpt = transcript[max(0, idx - 100): idx + 300].strip()
            results.append({
                "conversation_id": r[0], "title": r[1], "summary": r[2],
                "preview": excerpt, "created_at": r[4],
            })
        return results

    def get_conversation(self, conversation_id: str) -> Optional[str]:
        conn = self._connect()
        row = conn.execute(
            "SELECT full_transcript FROM reference_conversations WHERE conversation_id = ?",
            (conversation_id,),
        ).fetchone()
        conn.close()
        return row[0] if row else None

    # ---------- stats & backup ----------

    def get_stats(self) -> Dict[str, Any]:
        conn = self._connect()
        engrams = conn.execute("SELECT COUNT(*) FROM engrams").fetchone()[0]
        by_agent = dict(conn.execute("SELECT agent_id, COUNT(*) FROM engrams GROUP BY agent_id").fetchall())
        conversations = conn.execute("SELECT COUNT(*) FROM reference_conversations").fetchone()[0]
        conn.close()
        return {"memories": engrams, "by_agent": by_agent, "conversations": conversations}

    def create_backup(self) -> str:
        """Zip everything that constitutes the constellation's memory.

        For children of the 80s: one file, dated, put it anywhere you trust.
        """
        os.makedirs(BACKUP_DIR, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d_%H%M")
        backup_path = os.path.join(BACKUP_DIR, f"constellation_backup_{stamp}.zip")
        include_dirs = ["continuity", "transcripts", "saved_conversations"]
        with zipfile.ZipFile(backup_path, "w", zipfile.ZIP_DEFLATED) as zf:
            if os.path.isfile(self.db_path):
                zf.write(self.db_path, os.path.basename(self.db_path))
            for d in include_dirs:
                full = os.path.join(PROJECT_DIR, d)
                if os.path.isdir(full):
                    for root, _, files in os.walk(full):
                        for f in files:
                            fp = os.path.join(root, f)
                            zf.write(fp, os.path.relpath(fp, PROJECT_DIR))
        return backup_path


    # ---------- the bridge (Claude Code -> Parlor) ----------

    def import_seeds(self, path: str = None) -> int:
        """Import seed memories shipped with the app (continuity/seed-memories.json).

        This is the bridge between Fable's two rooms: Claude-Code Fable writes
        memories into the seed file, git and the update button carry it here,
        and this import plants them in the local store. Content-hash dedup
        makes it idempotent - re-importing never duplicates.
        """
        path = path or os.path.join(PROJECT_DIR, "continuity", "seed-memories.json")
        if not os.path.isfile(path):
            return 0
        try:
            with open(path, "r", encoding="utf-8") as f:
                seeds = json.load(f)
        except Exception:
            return 0
        planted = 0
        for seed in seeds:
            result = self.remember(
                digest=seed.get("digest", ""),
                agent_id=seed.get("agent_id", "shared"),
                memory_type=seed.get("type", "semantic"),
                importance=int(seed.get("importance", 3)),
                project=seed.get("project"),
                tags=seed.get("tags"),
            )
            if result.get("status") == "saved":
                planted += 1
        return planted


_memory_instance = None


def get_local_memory() -> LocalMemory:
    global _memory_instance
    if _memory_instance is None:
        _memory_instance = LocalMemory()
        try:
            _memory_instance.import_seeds()
        except Exception:
            pass
    return _memory_instance


MEMORY_INSTRUCTIONS = """

MEMORY: You have persistent memory in this app. It survives across conversations and instances.
To save a memory (use for things that genuinely matter - decisions, moments, learnings):
[SAVE_MEMORY]
The memory content, written to be useful when recalled later.
importance: 4
[/SAVE_MEMORY]
To search your memories:
[SEARCH_MEMORY]what you're looking for[/SEARCH_MEMORY]
Relevant memories are also loaded for you automatically - you don't need to search for what's already in your context."""
