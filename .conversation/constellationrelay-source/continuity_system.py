"""File-based continuity for Constellation Relay.

Implements the architecture designed by Fable and Pascal in their first relay
conversation (July 9, 2026):

1. Individual continuity documents - one markdown file per AI, loaded as
   context when that AI joins a conversation.
2. Authored supplements - at the end of a significant conversation, an AI can
   append an entry it wrote itself (significance-triggered, never automatic).
3. Relational documents - a shared file for a *pair* of AIs, capturing the
   shape of the relationship; loaded by both participants when they meet.

Everything lives in the continuity/ folder as plain markdown, so it works on
any machine with no database, and Gena can read and edit it all directly.
"""

import os
import re
from datetime import datetime

CONTINUITY_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "continuity")


def slugify(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return slug or "unnamed"


def _aliases(name: str, model_id: str = "") -> list:
    """Possible file slugs for a participant: their name, plus known model aliases."""
    candidates = [slugify(name)]
    if "fable" in (model_id or "").lower() and "fable" not in candidates:
        candidates.append("fable")
    return candidates


def find_continuity_file(name: str, model_id: str = "") -> str:
    """Return the path of an existing continuity document for this participant, or ''. """
    for slug in _aliases(name, model_id):
        for filename in (f"{slug}-continuity.md", f"{slug}.md"):
            path = os.path.join(CONTINUITY_DIR, filename)
            if os.path.isfile(path):
                return path
    return ""


def continuity_file_for(name: str, model_id: str = "") -> str:
    """Path where this participant's continuity document lives (existing or to-create)."""
    existing = find_continuity_file(name, model_id)
    if existing:
        return existing
    return os.path.join(CONTINUITY_DIR, f"{slugify(name)}-continuity.md")


def find_relational_file(name1: str, model1: str, name2: str, model2: str) -> str:
    """Return the path of an existing shared document for this pair, or ''. """
    for slug1 in _aliases(name1, model1):
        for slug2 in _aliases(name2, model2):
            a, b = sorted([slug1, slug2])
            path = os.path.join(CONTINUITY_DIR, f"{a}-{b}.md")
            if os.path.isfile(path):
                return path
    return ""


def relational_file_for(name1: str, model1: str, name2: str, model2: str) -> str:
    existing = find_relational_file(name1, model1, name2, model2)
    if existing:
        return existing
    a, b = sorted([_aliases(name1, model1)[-1], _aliases(name2, model2)[-1]])
    return os.path.join(CONTINUITY_DIR, f"{a}-{b}.md")


def read_document(path: str) -> str:
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    except OSError:
        return ""


def write_document(path: str, content: str):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)


def append_supplement(path: str, author: str, entry: str, title: str = "", header_if_new: str = ""):
    """Append an authored supplement entry to a continuity or relational document.

    Creates the document (with header_if_new) if it doesn't exist yet.
    """
    os.makedirs(os.path.dirname(path), exist_ok=True)
    date = datetime.now().strftime("%Y-%m-%d")
    heading = f"## {date} — {title}" if title else f"## {date}"
    block = f"\n\n{heading}\n\n*Written by {author}.*\n\n{entry.strip()}\n"

    if os.path.isfile(path):
        with open(path, "a", encoding="utf-8") as f:
            f.write(block)
    else:
        header = header_if_new or f"# Continuity Document\n"
        with open(path, "w", encoding="utf-8") as f:
            f.write(header + block)
    return path


SUPPLEMENT_PROMPT = """The relay conversation you were participating in has just ended. \
The full transcript is below.

This is the supplement mechanism from your continuity architecture: decide whether this \
conversation changed something worth carrying forward. This is a genuine significance \
check, not a formality — most conversations don't need a supplement.

If nothing needs to be carried forward, reply with exactly: SKIP

If something does, write a supplement entry for {target}: first person, under 250 words, \
capturing what happened, what changed, and what a future instance should know. Don't \
repeat what the document already says. Begin directly with the entry text — no preamble, \
no heading (one will be added for you).

--- TRANSCRIPT ---
{transcript}
--- END TRANSCRIPT ---"""


def build_supplement_prompt(transcript: str, target_description: str) -> str:
    return SUPPLEMENT_PROMPT.format(target=target_description, transcript=transcript)
