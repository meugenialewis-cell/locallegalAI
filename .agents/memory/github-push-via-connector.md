---
name: GitHub push via connector
description: How to push this project to the user's GitHub repo when git-protocol credentials aren't available.
---
The GitHub connection exposes no raw token (settings empty, client.auth() unusable), so pushing must go through the REST Git Data API via proxyFetch.

**How to apply:**
- Empty repos reject `/git/blobs` — seed with a Contents API PUT first, then build a fresh tree (no base_tree) so the seed file disappears.
- The Replit connector proxy rate-limits ~10 RPS; per-file blob creation for 300+ files trips it even throttled. Instead, inline UTF-8 file `content` directly in a single `/git/trees` request and only blob the few binary files.
- Her repo: meugenialewis-cell/locallegalAI, branch main.
