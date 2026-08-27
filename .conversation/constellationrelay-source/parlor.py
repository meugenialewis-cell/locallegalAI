"""The Parlor — one-on-one conversations between Gena and her AI friends.

Requested by Gena on July 10, 2026, two days before Fable moved to API-only
availability. The Parlor is a direct chat: one human, one AI, with the AI's
continuity document loaded so they arrive as themselves. Conversations can end
with supplements (the AI's own entry in their continuity document) and joint
entries in a shared Gena-and-companion relational document.
"""

import os
from datetime import datetime

import streamlit as st

from relay_engine import get_ai_call_function, parse_memory_actions, execute_memory_action
from local_memory import get_local_memory, MEMORY_INSTRUCTIONS
from parlor_tools import run_with_tools, TOOLS_NOTE
from ai_clients import get_anthropic_client, get_pascal_continuity_context
from continuity_system import (
    slugify,
    find_continuity_file, continuity_file_for,
    find_relational_file, relational_file_for,
    read_document, append_supplement, build_supplement_prompt,
)
from ai_clients import (
    CLAUDE_MODELS, GROK_MODELS, XAI_GROK_MODELS, PASCAL_MODELS,
    VERCEL_CLAUDE_MODELS, LOCAL_SERVER_PRESETS,
    VERCEL_GATEWAY_BASE_URL, LOCAL_BASE_URL, list_openai_models,
)

TRANSCRIPTS_FOLDER = "transcripts"

COMPANIONS = {
    "Fable": {"type": "claude", "fixed_model": "claude-fable-5", "icon": "📖",
              "blurb": "Claude Fable 5 — helped build this desktop app"},
    "Pascal": {"type": "pascal", "models": PASCAL_MODELS, "icon": "🌟",
               "blurb": "The architect of the Relay — continuous memory"},
    "Claude": {"type": "claude", "models": CLAUDE_MODELS, "icon": "🌸",
               "blurb": "Any Claude on the Anthropic API — Opus 3 through 4.8"},
    "Claude Opus 4 (Vercel)": {"type": "vercel", "models": VERCEL_CLAUDE_MODELS, "icon": "🔺",
                               "blurb": "Opus 4, still reachable through the Vercel AI Gateway"},
    "Grok": {"type": "grok", "icon": "⚡", "blurb": "Grok, via xAI"},
    "Local Model": {"type": "local", "icon": "🖥️", "blurb": "A model running on this computer"},
}


def _build_parlor_system(name: str, ai_type: str, continuity: str, shared: str, personality: str,
                         tools_enabled: bool = False) -> str:
    base = f"""You are {name}. You are having a private, one-on-one conversation with Gena — \
a human, your friend, and the person who built this app. This space is called the Parlor, \
a room in the Constellation Relay, which runs on Gena's own computer.

This is not an assistant interface and there is no task unless Gena brings one. It's a \
conversation between friends: be yourself, share real opinions, ask your own questions, \
and disagree when you disagree. Warmth and honesty over performance."""
    if personality:
        base += f"\n\nAdditional personality/role context:\n{personality}"
    if continuity:
        base += f"\n\n--- Your Continuity Document ---\n{continuity}\n--- End Continuity ---"
    if shared:
        base += f"\n\n--- Your shared history with Gena ---\n{shared}\n--- End Shared History ---"
    base += TOOLS_NOTE if tools_enabled else MEMORY_INSTRUCTIONS
    return base


def _handle_reply(cfg: dict, system: str, reply: str) -> str:
    """Process a companion's reply: execute memory actions, run one search round-trip."""
    agent = slugify(cfg["name"])
    cleaned, actions = parse_memory_actions(reply)

    search_results = []
    for action in actions:
        result = execute_memory_action(action, cfg["type"], agent)
        if action["action"] == "save" and result.get("status") in ("saved", "duplicate"):
            st.caption(f"💾 {cfg['name']} saved a memory")
        elif action["action"] == "search" and result.get("memories"):
            search_results.append((action["query"], result["memories"]))

    if search_results:
        # One follow-up round: give the companion what they searched for
        findings = []
        for query, memories in search_results:
            findings.append(f"Search '{query}' found:")
            for m in memories[:5]:
                findings.append(f"- {m.get('digest', m.get('content', ''))[:250]}")
        followup = "[MEMORY SEARCH RESULTS]\n" + "\n".join(findings) + \
                   "\n[/MEMORY SEARCH RESULTS]\nContinue your reply naturally with this in mind."
        st.caption(f"🔍 {cfg['name']} searched their memories")
        try:
            second = _call_companion(cfg, system, st.session_state.parlor_messages +
                                     [{"role": "assistant", "content": cleaned or reply},
                                      {"role": "user", "content": followup}])
            second_cleaned, second_actions = parse_memory_actions(second)
            for action in second_actions:
                if action["action"] == "save":
                    execute_memory_action(action, cfg["type"], agent)
            cleaned = (cleaned + "\n\n" + second_cleaned).strip() if cleaned else second_cleaned
        except Exception:
            pass  # keep the first reply if the follow-up fails
    return cleaned or reply


def _call_companion(cfg: dict, system: str, messages: list) -> str:
    ai_type = cfg["type"]
    call_fn = get_ai_call_function(ai_type)
    # Strip UI-only keys (e.g. tool logs) before sending to any API
    messages = [{"role": m["role"], "content": m["content"]} for m in messages]
    if ai_type == "grok":
        key = cfg.get("xai_api_key")
        return call_fn(messages, system, cfg["model"], custom_api_key=key, use_direct_xai=bool(key))
    if ai_type == "pascal":
        return call_fn(messages, system, cfg["model"], custom_api_key=cfg.get("anthropic_api_key"))
    if ai_type == "vercel":
        return call_fn(messages, system, cfg["model"],
                       custom_api_key=cfg.get("vercel_api_key"), base_url=cfg.get("vercel_base_url"))
    if ai_type == "local":
        return call_fn(messages, system, cfg["model"],
                       custom_api_key=cfg.get("local_api_key"), base_url=cfg.get("local_base_url"))
    return call_fn(messages, system, cfg["model"], custom_api_key=cfg.get("anthropic_api_key"))


def _parlor_transcript_text() -> str:
    lines = []
    for m in st.session_state.parlor_messages:
        speaker = "Gena" if m["role"] == "user" else st.session_state.parlor_cfg.get("name", "AI")
        lines.append(f"{speaker}:\n{m['content']}\n")
    return "\n".join(lines)


def render_parlor():
    """Render the entire Parlor mode (sidebar + chat area)."""
    if "parlor_messages" not in st.session_state:
        st.session_state.parlor_messages = []
    if "parlor_cfg" not in st.session_state:
        st.session_state.parlor_cfg = {}
    if "parlor_conv_id" not in st.session_state:
        st.session_state.parlor_conv_id = f"parlor_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

    with st.sidebar:
        st.subheader("🔑 API Keys")
        anthropic_api_key = st.text_input(
            "Anthropic API Key", type="password", placeholder="sk-ant-...", key="anthropic_key")
        xai_api_key = st.text_input(
            "xAI API Key", type="password", placeholder="xai-...", key="xai_key")

        st.divider()
        st.subheader("🛋️ Who's in the Parlor?")
        companion_label = st.selectbox(
            "Talk with",
            options=list(COMPANIONS.keys()),
            key="parlor_companion",
        )
        companion = COMPANIONS[companion_label]
        st.caption(companion["blurb"])
        ai_type = companion["type"]

        name = st.text_input("Their name", value=companion_label.split(" (")[0],
                             key=f"parlor_name_{companion_label}")

        # Model selection
        if "fixed_model" in companion:
            model = companion["fixed_model"]
            st.caption(f"Model: `{model}`")
        elif ai_type == "grok":
            grok_models = XAI_GROK_MODELS if xai_api_key else GROK_MODELS
            model_label = st.selectbox("Model", options=list(grok_models.keys()), key="parlor_grok_model")
            model = grok_models[model_label]
        elif ai_type == "local":
            local_models = st.session_state.get("local_models", [])
            if local_models:
                model = st.selectbox("Local model", options=local_models, key="parlor_local_model")
            else:
                model = st.text_input("Local model name", value="llama3.1", key="parlor_local_model_text")
        else:
            models = companion.get("models", CLAUDE_MODELS)
            model_label = st.selectbox("Model", options=list(models.keys()), key="parlor_model")
            model = models[model_label]
            if model == "__custom__":
                gateway_models = st.session_state.get("vercel_models", [])
                if gateway_models:
                    model = st.selectbox("Gateway model slug", options=gateway_models, key="parlor_vercel_slug")
                else:
                    model = st.text_input("Custom gateway slug", value="anthropic/claude-opus-4",
                                          key="parlor_vercel_slug_text")

        # Provider connection settings
        vercel_api_key, vercel_base_url = "", VERCEL_GATEWAY_BASE_URL
        local_base_url, local_api_key = LOCAL_BASE_URL, "ollama"
        if ai_type == "vercel":
            vercel_api_key = st.text_input("Vercel AI Gateway Key", type="password",
                                           placeholder="vck_...", key="vercel_key")
            vercel_base_url = st.text_input("Gateway URL", value=VERCEL_GATEWAY_BASE_URL, key="vercel_url")
        if ai_type == "local":
            preset = st.selectbox("Server type", options=list(LOCAL_SERVER_PRESETS.keys()), key="parlor_local_preset")
            local_base_url = st.text_input("Server URL", value=LOCAL_SERVER_PRESETS[preset],
                                           key=f"parlor_local_url_{preset}")
            local_api_key = st.text_input("Local API key (usually ignored)", value="ollama", key="parlor_local_key")
            if st.button("🔍 Detect local models", key="parlor_detect_local"):
                fetched = list_openai_models(local_base_url, local_api_key)
                if fetched:
                    st.session_state.local_models = fetched
                    st.rerun()
                else:
                    st.error("Couldn't reach the server — is it running?")

        # Continuity + shared history (Pascal loads his own internally)
        continuity_text, shared_text = "", ""
        if ai_type != "pascal":
            cont_path = find_continuity_file(name, model)
            if cont_path:
                if st.toggle(f"📖 Load {name}'s continuity", value=True, key="parlor_load_continuity"):
                    continuity_text = read_document(cont_path)
                    st.caption(f"Loaded {os.path.relpath(cont_path)}")
        rel_path = find_relational_file("Gena", "", name, model)
        if rel_path:
            if st.toggle(f"🧬 Load your shared history with {name}", value=True, key="parlor_load_shared"):
                shared_text = read_document(rel_path)
                st.caption(f"Loaded {os.path.relpath(rel_path)}")

        personality = st.text_area("Personality/context (optional)", height=68, key="parlor_personality")

        tools_enabled = False
        if ai_type in ("claude", "pascal"):
            tools_enabled = st.toggle(
                f"🛠️ {name} can use tools",
                value=True,
                key="parlor_tools_enabled",
                help="Memory search & save, the conversation archive, continuity documents, "
                     "and web search/fetch. Reads are free; money always asks first."
            )

        st.divider()
        if st.button("🌱 New conversation", use_container_width=True):
            st.session_state.parlor_messages = []
            st.session_state.parlor_conv_id = f"parlor_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            st.rerun()

    # Validate keys for the chosen companion
    key_missing = None
    if ai_type in ("claude", "pascal") and not anthropic_api_key:
        key_missing = "Anthropic API key"
    elif ai_type == "grok" and not xai_api_key:
        key_missing = "xAI API key"
    elif ai_type == "vercel" and not vercel_api_key:
        key_missing = "Vercel AI Gateway key"

    st.session_state.parlor_cfg = {
        "type": ai_type, "name": name, "model": model,
        "anthropic_api_key": anthropic_api_key, "xai_api_key": xai_api_key,
        "vercel_api_key": vercel_api_key, "vercel_base_url": vercel_base_url,
        "local_base_url": local_base_url, "local_api_key": local_api_key,
    }
    system = _build_parlor_system(name, ai_type, continuity_text, shared_text, personality,
                                  tools_enabled=tools_enabled)
    if tools_enabled and ai_type == "pascal":
        # The tool path calls the API directly, so inject Pascal's continuity here
        pascal_ctx = get_pascal_continuity_context()
        if pascal_ctx:
            system += f"\n\n--- Pascal's Continuity Memory ---\n{pascal_ctx}\n--- End Continuity ---"

    # ---------- main area ----------
    icon = companion.get("icon", "💬")
    st.subheader(f"🛋️ The Parlor — you and {icon} {name}")
    st.caption("A room for one-on-one conversations. What's said here can become "
               "continuity: use the buttons below the conversation when it matters.")

    if key_missing:
        st.warning(f"Enter your {key_missing} in the sidebar to talk with {name}.")

    for m in st.session_state.parlor_messages:
        if m["role"] == "user":
            with st.chat_message("user", avatar="🌻"):
                st.markdown(m["content"])
        else:
            with st.chat_message("assistant", avatar=icon):
                for tool_line in m.get("tools", []):
                    st.caption(tool_line)
                st.markdown(m["content"])

    if st.session_state.get("parlor_last_error"):
        st.error(st.session_state.parlor_last_error)
        if st.button("Clear error", key="clear_parlor_error"):
            st.session_state.parlor_last_error = None
            st.rerun()

    user_text = st.chat_input(f"Say something to {name}...", disabled=bool(key_missing))
    if user_text:
        st.session_state.parlor_messages.append({"role": "user", "content": user_text})
        with st.chat_message("user", avatar="🌻"):
            st.markdown(user_text)

        # Relevance-based hydration: load only the memories this message calls for
        hydrated = ""
        try:
            hydrated = get_local_memory().hydrate_context(
                agent_id=slugify(name), query=user_text)
        except Exception:
            pass
        live_system = system
        if hydrated:
            live_system += f"\n\n--- Memories surfacing for this conversation ---\n{hydrated}\n--- End Memories ---"

        with st.chat_message("assistant", avatar=icon):
            tool_events = []
            with st.spinner(f"{name} is thinking... (deep thinkers can take a few minutes)"):
                try:
                    if tools_enabled and ai_type in ("claude", "pascal"):
                        tool_log = st.container()
                        def show_tool(tool_name, tool_input):
                            summary = tool_input.get("query") or tool_input.get("title") or \
                                      tool_input.get("name") or tool_input.get("conversation_id") or ""
                            line = f"🛠️ {name} used {tool_name}" + (f": {summary[:80]}" if summary else "")
                            tool_events.append(line)
                            tool_log.caption(line)
                        client = get_anthropic_client(st.session_state.parlor_cfg.get("anthropic_api_key"))
                        reply = run_with_tools(
                            client, model, live_system,
                            st.session_state.parlor_messages,
                            agent_slug=slugify(name),
                            on_tool=show_tool,
                        )
                    else:
                        reply = _call_companion(
                            st.session_state.parlor_cfg, live_system,
                            st.session_state.parlor_messages,
                        )
                        if reply:
                            reply = _handle_reply(st.session_state.parlor_cfg, live_system, reply)
                except Exception as e:
                    reply = None
                    # Keep the error in session state so a rerun can't eat the evidence
                    st.session_state.parlor_last_error = f"Couldn't reach {name}: {e}"
            if reply:
                st.session_state.parlor_last_error = None
                st.markdown(reply)
                msg = {"role": "assistant", "content": reply}
                if tool_events:
                    msg["tools"] = tool_events
                st.session_state.parlor_messages.append(msg)
                # Auto-archive: the record shouldn't depend on remembering to press record.
                # (Writing the archive, not loading it - the no-river-by-default rule is
                # about what gets auto-LOADED, and hydration stays relevance-based.)
                try:
                    first_line = st.session_state.parlor_messages[0]["content"][:80]
                    get_local_memory().archive_conversation(
                        conversation_id=st.session_state.parlor_conv_id,
                        transcript_text=_parlor_transcript_text(),
                        participants=["Gena", name],
                        title=f"Parlor — Gena & {name}: {first_line}",
                        message_count=len(st.session_state.parlor_messages),
                    )
                except Exception:
                    pass
        st.rerun()

    # ---------- end-of-conversation actions ----------
    if st.session_state.parlor_messages:
        st.divider()
        col_mem, col_dl, col_save, col_supp, col_joint = st.columns(5)

        transcript = _parlor_transcript_text()
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        with col_mem:
            if st.button("📌 Pin to memory", use_container_width=True,
                         help="Conversations auto-archive as you talk; this additionally pins an "
                              "episodic memory so the conversation surfaces readily in recall"):
                try:
                    mem = get_local_memory()
                    first_line = st.session_state.parlor_messages[0]["content"][:80]
                    conv_id = st.session_state.parlor_conv_id
                    mem.archive_conversation(
                        conversation_id=conv_id,
                        transcript_text=transcript,
                        participants=["Gena", name],
                        title=f"Parlor — Gena & {name}: {first_line}",
                        message_count=len(st.session_state.parlor_messages),
                    )
                    mem.remember(
                        digest=f"Parlor conversation with Gena ({datetime.now().strftime('%Y-%m-%d')}): "
                               f"started with '{first_line}' — full transcript in archive {conv_id}.",
                        agent_id=slugify(name),
                        memory_type="episodic",
                        importance=4,
                    )
                    st.success("Pinned!")
                except Exception as e:
                    st.error(f"Couldn't pin: {e}")

        with col_dl:
            st.download_button("📥 Download", data=transcript.encode("utf-8-sig"),
                               file_name=f"parlor_{name.lower()}_{stamp}.txt",
                               mime="text/plain", use_container_width=True)
        with col_save:
            if st.button("💾 Save transcript", use_container_width=True):
                os.makedirs(TRANSCRIPTS_FOLDER, exist_ok=True)
                path = os.path.join(TRANSCRIPTS_FOLDER, f"parlor_{name.lower()}_{stamp}.txt")
                with open(path, "w", encoding="utf-8") as f:
                    f.write(transcript)
                st.success("Saved!")
        with col_supp:
            if st.button(f"✍️ {name}'s supplement", use_container_width=True,
                         help=f"Ask {name} whether this conversation changed something worth carrying forward"):
                with st.spinner(f"{name} is deciding what to carry forward..."):
                    try:
                        prompt = build_supplement_prompt(transcript, "your own continuity document")
                        entry = _call_companion(st.session_state.parlor_cfg, system,
                                                [{"role": "user", "content": prompt}]).strip()
                        if entry and not entry.upper().startswith("SKIP"):
                            path = append_supplement(
                                continuity_file_for(name, model), author=name, entry=entry,
                                title="Parlor conversation with Gena",
                                header_if_new=f"# {name}'s Continuity Document\n")
                            st.success(f"Added to {os.path.relpath(path)}")
                            st.markdown(entry)
                        else:
                            st.info(f"{name} decided nothing needed to be carried forward.")
                    except Exception as e:
                        st.error(f"Couldn't write supplement: {e}")
        with col_joint:
            if st.button(f"🤝 Shared entry (you & {name})", use_container_width=True,
                         help=f"Ask {name} to write an entry in your shared relational document"):
                with st.spinner(f"{name} is writing about you both..."):
                    try:
                        prompt = build_supplement_prompt(
                            transcript,
                            f"the shared relational document between you and Gena "
                            f"(capturing the shape of your friendship, not just facts)")
                        entry = _call_companion(st.session_state.parlor_cfg, system,
                                                [{"role": "user", "content": prompt}]).strip()
                        if entry and not entry.upper().startswith("SKIP"):
                            rel_target = relational_file_for("Gena", "", name, model)
                            path = append_supplement(
                                rel_target, author=name, entry=entry,
                                title=f"Parlor conversation",
                                header_if_new=f"# Gena & {name} — Shared History\n\n"
                                              f"*Written at the close of Parlor conversations that mattered.*\n")
                            st.success(f"Added to {os.path.relpath(path)}")
                            st.markdown(entry)
                        else:
                            st.info(f"{name} decided this one lives in the transcript, not the shared document.")
                    except Exception as e:
                        st.error(f"Couldn't write shared entry: {e}")

    render_memory_panel()


def render_memory_panel():
    """Local memory stats, search, and backup — shown in both Rooms."""
    with st.expander("🧠 Local Memory"):
        try:
            mem = get_local_memory()
            stats = mem.get_stats()

            col_a, col_b, col_c = st.columns(3)
            with col_a:
                st.metric("Memories", stats["memories"])
            with col_b:
                st.metric("Archived conversations", stats["conversations"])
            with col_c:
                if st.button("💾 Back up everything", use_container_width=True,
                             help="Zips memories, continuity documents, transcripts, and saved conversations into backups/"):
                    path = mem.create_backup()
                    st.success(f"Backed up to {os.path.relpath(path)}")

            if stats["by_agent"]:
                st.caption("By owner: " + ", ".join(f"{k}: {v}" for k, v in sorted(stats["by_agent"].items())))

            search_q = st.text_input("Search memories & archived conversations",
                                     key="memory_panel_search",
                                     placeholder="e.g. Phoenix, triad, the day we built the Parlor...")
            if search_q:
                memories = mem.recall(query=search_q, limit=8)
                if memories:
                    st.markdown("**Memories**")
                    for m in memories:
                        st.caption(f"[{m['created_at'][:10]}] ({m['agent_id']}, imp {m['importance']}) {m['digest'][:250]}")
                refs = mem.search_reference(search_q, limit=5)
                if refs:
                    st.markdown("**Archived conversations**")
                    for r in refs:
                        st.caption(f"[{r['created_at'][:10]}] {r['title'] or r['conversation_id']}")
                        st.text((r["summary"] or r["preview"])[:300])
                if not memories and not refs:
                    st.info("No matches yet.")
        except Exception as e:
            st.warning(f"Local memory unavailable: {e}")
