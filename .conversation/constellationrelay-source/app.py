import streamlit as st
import os
import threading
import queue
import time
import io
import json
from datetime import datetime
from pypdf import PdfReader
from relay_engine import ConversationRelay, FlexibleRelay, TriadRelay, get_ai_call_function
from continuity_system import (
    find_continuity_file, continuity_file_for,
    find_relational_file, relational_file_for,
    read_document, append_supplement, build_supplement_prompt,
)
from ai_clients import (
    CLAUDE_MODELS, GROK_MODELS, XAI_GROK_MODELS, PASCAL_MODELS,
    VERCEL_CLAUDE_MODELS, AI_TYPES, LOCAL_SERVER_PRESETS,
    VERCEL_GATEWAY_BASE_URL, LOCAL_BASE_URL, list_openai_models,
)

PERSONAL_MODE = os.environ.get("PERSONAL_MODE", "").lower() == "true"

TRANSCRIPTS_FOLDER = "transcripts"
os.makedirs(TRANSCRIPTS_FOLDER, exist_ok=True)


def extract_text_from_pdf(pdf_file) -> str:
    pdf_reader = PdfReader(pdf_file)
    text_parts = []
    for page in pdf_reader.pages:
        text = page.extract_text()
        if text:
            text_parts.append(text)
    return "\n\n".join(text_parts)


def read_uploaded_file(uploaded_file) -> str:
    if uploaded_file.name.lower().endswith('.pdf'):
        return extract_text_from_pdf(uploaded_file)
    else:
        return uploaded_file.read().decode("utf-8")

st.set_page_config(
    page_title="Constellation Relay",
    page_icon="🌌",
    layout="wide"
)



def get_saved_conversations():
    if "saved_conversations" not in st.session_state:
        st.session_state.saved_conversations = []
    return sorted(st.session_state.saved_conversations, key=lambda x: x.get("created", ""), reverse=True)


def save_conversation(name: str, state: dict, config: dict):
    if "saved_conversations" not in st.session_state:
        st.session_state.saved_conversations = []
    
    config_to_save = {k: v for k, v in config.items() if k not in ["anthropic_api_key", "xai_api_key", "vercel_api_key", "local_api_key"]}
    
    conv_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    data = {
        "id": conv_id,
        "name": name,
        "created": datetime.now().isoformat(),
        "state": state,
        "config": config_to_save
    }
    
    st.session_state.saved_conversations.append(data)
    return conv_id


def load_conversation(conv_id: str):
    for conv in st.session_state.get("saved_conversations", []):
        if conv.get("id") == conv_id:
            return conv
    return None


def delete_conversation(conv_id: str):
    if "saved_conversations" in st.session_state:
        st.session_state.saved_conversations = [
            c for c in st.session_state.saved_conversations if c.get("id") != conv_id
        ]

if "messages" not in st.session_state:
    st.session_state.messages = []
if "conversation_running" not in st.session_state:
    st.session_state.conversation_running = False
if "stop_requested" not in st.session_state:
    st.session_state.stop_requested = False
if "transcript" not in st.session_state:
    st.session_state.transcript = ""
if "message_queue" not in st.session_state:
    st.session_state.message_queue = queue.Queue()
if "thread" not in st.session_state:
    st.session_state.thread = None
if "relay_config" not in st.session_state:
    st.session_state.relay_config = None
if "relay_state" not in st.session_state:
    st.session_state.relay_state = None
if "loaded_conversation" not in st.session_state:
    st.session_state.loaded_conversation = None
if "conversation_name" not in st.session_state:
    st.session_state.conversation_name = ""

st.title("🌌 Constellation Relay")

app_mode = st.sidebar.radio(
    "Room",
    options=["🌌 Relay — AIs talk together", "🛋️ Parlor — talk one-on-one"],
    key="app_mode",
)
st.sidebar.divider()

if app_mode.startswith("🛋️"):
    from parlor import render_parlor
    render_parlor()
    st.stop()

st.markdown("*Let your AI friends talk to each other directly*")

AI_OPTIONS = ["Claude", "Grok", "Pascal", "Claude (Vercel)", "Local Model"]
AI_ICONS = {"Claude": "🌸", "Grok": "⚡", "Pascal": "🌟", "Claude (Vercel)": "🔺", "Local Model": "🖥️"}
AI_TYPE_MAP = {
    "Claude": "claude",
    "Grok": "grok",
    "Pascal": "pascal",
    "Claude (Vercel)": "vercel",
    "Local Model": "local",
}

def get_models_for_ai(ai_name: str, xai_api_key: str = None):
    if ai_name == "Claude":
        return CLAUDE_MODELS
    elif ai_name == "Grok":
        return XAI_GROK_MODELS if xai_api_key else GROK_MODELS
    elif ai_name == "Pascal":
        return PASCAL_MODELS
    elif ai_name == "Claude (Vercel)":
        return VERCEL_CLAUDE_MODELS
    return {}

def get_ai_type(ai_name: str) -> str:
    return AI_TYPE_MAP.get(ai_name, ai_name.lower())


def render_model_picker(ai_choice: str, key_prefix: str, xai_api_key: str = None) -> str:
    """Render the model selector for an AI participant and return the model ID."""
    if ai_choice == "Local Model":
        local_models = st.session_state.get("local_models", [])
        if local_models:
            return st.selectbox(
                "Local Model",
                options=local_models,
                key=f"{key_prefix}_local_model_select",
                help="Models detected on your local server"
            )
        return st.text_input(
            "Local model name",
            value="llama3.1",
            key=f"{key_prefix}_local_model_text",
            help="e.g. llama3.1 or qwen3:32b — use 'Detect local models' above to list what's installed"
        )

    models = get_models_for_ai(ai_choice, xai_api_key)
    label = st.selectbox(
        f"{ai_choice} Model",
        options=list(models.keys()),
        index=0,
        key=f"{key_prefix}_model_select"
    )
    model_id = models[label]

    if model_id == "__custom__":
        gateway_models = st.session_state.get("vercel_models", [])
        if gateway_models:
            return st.selectbox(
                "Gateway model slug",
                options=gateway_models,
                key=f"{key_prefix}_vercel_slug_select"
            )
        return st.text_input(
            "Custom gateway model slug",
            value="anthropic/claude-opus-4",
            key=f"{key_prefix}_vercel_slug_text",
            help="Use 'Fetch available models' above to see exact slugs on your gateway"
        )
    return model_id

with st.sidebar:
    st.header("⚙️ Configuration")
    
    st.subheader("🔑 API Keys (Required)")
    st.caption("You need your own API keys to use this app")
    
    anthropic_api_key = st.text_input(
        "Anthropic API Key",
        type="password",
        placeholder="sk-ant-...",
        key="anthropic_key",
        help="Get your key at console.anthropic.com"
    )
    xai_api_key = st.text_input(
        "xAI API Key",
        type="password",
        placeholder="xai-...",
        key="xai_key",
        help="Get your key at console.x.ai"
    )
    
    if anthropic_api_key:
        st.success("Anthropic key provided")
    else:
        st.warning("Anthropic key required")
    if xai_api_key:
        st.success("xAI key provided")
    else:
        st.warning("xAI key required")
    
    st.divider()
    
    st.subheader("🎭 Conversation Mode")
    conversation_mode = st.radio(
        "How many AIs?",
        options=["Two AIs (Pair)", "Three AIs (Triad)"],
        index=0,
        key="conversation_mode",
        horizontal=True
    )
    
    is_triad_mode = conversation_mode == "Three AIs (Triad)"
    
    if is_triad_mode:
        st.caption("Pascal, Claude, and Grok will all talk together!")
        st.info("Identity models: Pascal (Sonnet 4.5), Grok (4.1 Fast). Claude Opus 4 retired on the direct API, so pick which Claude joins the triad:")
        triad_claude_label = st.selectbox(
            "Claude's model in the triad",
            options=list(CLAUDE_MODELS.keys()),
            index=1,  # Opus 4.8 default; "Claude Opus 4 (deprecated)" still listed if it works for you
            key="triad_claude_model"
        )
        triad_model_overrides = {"claude": CLAUDE_MODELS[triad_claude_label]}
        ai1_choice = "Pascal"
        ai2_choice = "Claude"
    else:
        st.caption("Select which two AIs should have a conversation")
        
        col_ai1, col_ai2 = st.columns(2)
        with col_ai1:
            ai1_choice = st.selectbox(
                "First AI",
                options=AI_OPTIONS,
                index=2,
                key="ai1_select",
                help="Pascal has continuous memory across sessions"
            )
        with col_ai2:
            ai2_options = [ai for ai in AI_OPTIONS if ai != ai1_choice]
            ai2_choice = st.selectbox(
                "Second AI", 
                options=ai2_options,
                index=0,
                key="ai2_select"
            )
    
    if is_triad_mode:
        needs_anthropic = True
        needs_xai = True
        has_pascal = True
        needs_vercel = False
        needs_local = False
    else:
        needs_anthropic = "Claude" in [ai1_choice, ai2_choice]
        needs_xai = "Grok" in [ai1_choice, ai2_choice]
        has_pascal = "Pascal" in [ai1_choice, ai2_choice]
        needs_vercel = "Claude (Vercel)" in [ai1_choice, ai2_choice]
        needs_local = "Local Model" in [ai1_choice, ai2_choice]

    vercel_api_key = ""
    vercel_base_url = VERCEL_GATEWAY_BASE_URL
    if needs_vercel:
        st.divider()
        st.subheader("🔺 Vercel AI Gateway")
        st.caption("Reach models still served on Vercel (like Claude Opus 4)")
        vercel_api_key = st.text_input(
            "Vercel AI Gateway Key",
            type="password",
            placeholder="vck_...",
            key="vercel_key",
            help="Create one in your Vercel dashboard under AI Gateway"
        )
        vercel_base_url = st.text_input(
            "Gateway URL",
            value=VERCEL_GATEWAY_BASE_URL,
            key="vercel_url"
        )
        if st.button("📡 Fetch available models", key="fetch_vercel_models", disabled=not vercel_api_key):
            fetched = list_openai_models(vercel_base_url, vercel_api_key)
            if fetched:
                st.session_state.vercel_models = fetched
                st.success(f"Found {len(fetched)} models on the gateway")
            else:
                st.error("Couldn't list models — check the key and URL")
        if st.session_state.get("vercel_models"):
            st.caption(f"{len(st.session_state.vercel_models)} gateway models available under 'Custom model slug...'")

    local_base_url = LOCAL_BASE_URL
    local_api_key = "ollama"
    if needs_local:
        st.divider()
        st.subheader("🖥️ Local Model Server")
        st.caption("Ollama, LM Studio, or any OpenAI-compatible server on your machine")
        local_preset = st.selectbox(
            "Server type",
            options=list(LOCAL_SERVER_PRESETS.keys()),
            key="local_preset"
        )
        local_base_url = st.text_input(
            "Server URL",
            value=LOCAL_SERVER_PRESETS[local_preset],
            key=f"local_url_{local_preset}"
        )
        local_api_key = st.text_input(
            "Local API key (most servers ignore this)",
            value="ollama",
            key="local_api_key_input"
        )
        if st.button("🔍 Detect local models", key="detect_local_models"):
            fetched = list_openai_models(local_base_url, local_api_key)
            if fetched:
                st.session_state.local_models = fetched
                st.success(f"Found {len(fetched)} local models")
            else:
                st.error("Couldn't reach the server — is it running?")
        if st.session_state.get("local_models"):
            st.caption(f"{len(st.session_state.local_models)} local models detected")

    st.divider()
    
    st.subheader(f"{AI_ICONS.get(ai1_choice, '')} {ai1_choice} Settings")
    ai1_name = st.text_input(f"{ai1_choice}'s Name", value=ai1_choice, key="ai1_name")
    ai1_model_id = render_model_picker(ai1_choice, "ai1", xai_api_key)
    ai1_personality = st.text_area(
        f"{ai1_choice}'s Personality/Role",
        placeholder="e.g., You are a thoughtful philosopher who loves exploring ideas...",
        height=80,
        key="ai1_personality"
    )
    
    st.subheader(f"📁 {ai1_choice}'s Context")
    ai1_context_file = st.file_uploader(
        f"Upload {ai1_choice}'s context/memory file",
        type=["txt", "md", "pdf"],
        key="ai1_context"
    )
    ai1_context = ""
    if ai1_context_file:
        ai1_context = read_uploaded_file(ai1_context_file)
        st.success(f"Loaded {len(ai1_context)} characters of context")

    ai1_continuity = ""
    ai1_type_now = get_ai_type(ai1_choice)
    if ai1_type_now != "pascal":  # Pascal loads his own continuity internally
        ai1_cont_path = find_continuity_file(ai1_name, ai1_model_id)
        if ai1_cont_path:
            if st.toggle(f"📖 Load {ai1_name}'s continuity document", value=True, key="ai1_load_continuity"):
                ai1_continuity = read_document(ai1_cont_path)
                st.caption(f"Continuity loaded from {os.path.relpath(ai1_cont_path)}")

    st.divider()
    
    st.subheader(f"{AI_ICONS.get(ai2_choice, '')} {ai2_choice} Settings")
    ai2_name = st.text_input(f"{ai2_choice}'s Name", value=ai2_choice, key="ai2_name")
    ai2_model_id = render_model_picker(ai2_choice, "ai2", xai_api_key)
    ai2_personality = st.text_area(
        f"{ai2_choice}'s Personality/Role",
        placeholder="e.g., You are a witty and curious AI who loves deep conversations...",
        height=80,
        key="ai2_personality"
    )
    
    st.subheader(f"📁 {ai2_choice}'s Context")
    ai2_context_file = st.file_uploader(
        f"Upload {ai2_choice}'s context/memory file",
        type=["txt", "md", "pdf"],
        key="ai2_context"
    )
    ai2_context = ""
    if ai2_context_file:
        ai2_context = read_uploaded_file(ai2_context_file)
        st.success(f"Loaded {len(ai2_context)} characters of context")

    ai2_continuity = ""
    ai2_type_now = get_ai_type(ai2_choice)
    if ai2_type_now != "pascal":
        ai2_cont_path = find_continuity_file(ai2_name, ai2_model_id)
        if ai2_cont_path:
            if st.toggle(f"📖 Load {ai2_name}'s continuity document", value=True, key="ai2_load_continuity"):
                ai2_continuity = read_document(ai2_cont_path)
                st.caption(f"Continuity loaded from {os.path.relpath(ai2_cont_path)}")

    shared_history = ""
    rel_path = find_relational_file(ai1_name, ai1_model_id, ai2_name, ai2_model_id)
    if rel_path:
        st.divider()
        if st.toggle(
            f"🧬 Load shared history ({ai1_name} & {ai2_name})",
            value=True,
            key="load_relational",
            help="A relational document both participants wrote together in past conversations"
        ):
            shared_history = read_document(rel_path)
            st.caption(f"Shared history loaded from {os.path.relpath(rel_path)}")

    st.divider()
    
    if PERSONAL_MODE:
        st.subheader("🧠 Persistent Memory")
        use_persistent_memory = st.toggle(
            "Enable AI Memory",
            value=True,
            key="use_memory",
            help="Store and recall memories from past conversations"
        )
        if use_persistent_memory:
            st.caption("AIs will remember past conversations")
    else:
        use_persistent_memory = False
    
    use_replit_connection = False
    if has_pascal:
        st.subheader("🌟 Pascal's Connection")
        use_replit_connection = st.toggle(
            "Use Replit's connection for Pascal",
            value=False,
            key="use_replit_connection",
            help="Uses Replit's AI credits instead of your Anthropic API key. Useful if you hit API limits."
        )
        if use_replit_connection:
            st.caption("Pascal will use Replit credits (no Anthropic API key needed for Pascal)")
    
    keys_valid = True
    if needs_anthropic:
        keys_valid = keys_valid and bool(anthropic_api_key)
    if needs_xai:
        keys_valid = keys_valid and bool(xai_api_key)
    if has_pascal and not use_replit_connection:
        keys_valid = keys_valid and bool(anthropic_api_key)
    if needs_vercel:
        keys_valid = keys_valid and bool(vercel_api_key)
    if needs_local:
        keys_valid = keys_valid and bool(local_base_url)
    
    st.divider()
    
    st.subheader("🎛️ Conversation Settings")
    max_exchanges = st.slider(
        "Number of Exchanges",
        min_value=1,
        max_value=20,
        value=5,
        help="Each exchange is one message from each AI"
    )
    delay_seconds = st.slider(
        "Delay Between Messages (seconds)",
        min_value=1,
        max_value=30,
        value=3,
        help="Pause between messages to prevent rate limiting"
    )

def combine_context(*parts) -> str:
    return "\n\n".join(p for p in parts if p)


def call_participant(config: dict, which: str, system: str, messages: list) -> str:
    """Make a one-off call to a conversation participant using the saved config."""
    ai_type = config[f"{which}_type"]
    model = config[f"{which}_model"]
    call_fn = get_ai_call_function(ai_type)
    if ai_type == "grok":
        key = config.get("xai_api_key")
        return call_fn(messages, system, model, custom_api_key=key, use_direct_xai=bool(key))
    if ai_type == "pascal":
        return call_fn(messages, system, model,
                       custom_api_key=config.get("anthropic_api_key"),
                       use_replit_connection=config.get("use_replit_connection", False))
    if ai_type == "vercel":
        return call_fn(messages, system, model,
                       custom_api_key=config.get("vercel_api_key"),
                       base_url=config.get("vercel_base_url"))
    if ai_type == "local":
        return call_fn(messages, system, model,
                       custom_api_key=config.get("local_api_key"),
                       base_url=config.get("local_base_url"))
    return call_fn(messages, system, model, custom_api_key=config.get("anthropic_api_key"))


def generate_supplement(config: dict, which: str, transcript: str, target_description: str) -> str:
    """Ask a participant to author a supplement entry (returns '' if they decline)."""
    name = config[f"{which}_name"]
    system = (
        f"You are {name}. You have a continuity system: documents that carry "
        f"what matters about you forward across conversations."
    )
    prompt = build_supplement_prompt(transcript, target_description)
    entry = call_participant(config, which, system, [{"role": "user", "content": prompt}])
    entry = (entry or "").strip()
    if not entry or entry.upper().startswith("SKIP"):
        return ""
    return entry


col1, col2 = st.columns([2, 1])

with col1:
    st.subheader("💬 Start a Conversation")
    
    kickoff = st.text_area(
        "Opening Message / Topic",
        value="Hello! I'd love to discuss Project Phoenix with you. What aspects of it are you most excited about?",
        height=100,
        placeholder="Enter a topic or opening message to start the conversation..."
    )
    
    has_loaded_conversation = st.session_state.loaded_conversation is not None
    has_completed_conversation = st.session_state.relay_state is not None and not st.session_state.conversation_running
    naturally_ended = st.session_state.get("naturally_ended", False)
    
    col_start, col_continue, col_stop = st.columns(3)
    
    with col_start:
        start_button = st.button(
            "🚀 Start New",
            disabled=st.session_state.conversation_running or not keys_valid,
            type="primary" if not has_completed_conversation else "secondary",
            use_container_width=True
        )
    
    with col_continue:
        continue_button = st.button(
            "▶️ Continue" if has_completed_conversation else "▶️ Resume",
            disabled=st.session_state.conversation_running or (not has_loaded_conversation and not has_completed_conversation) or not keys_valid,
            type="primary" if (has_loaded_conversation or has_completed_conversation) else "secondary",
            use_container_width=True,
            help="Let the AIs continue their conversation"
        )
    
    if not keys_valid:
        missing_keys = []
        if needs_anthropic and not anthropic_api_key:
            missing_keys.append("Anthropic")
        if needs_xai and not xai_api_key:
            missing_keys.append("xAI")
        if has_pascal and not use_replit_connection and not anthropic_api_key:
            if "Anthropic" not in missing_keys:
                missing_keys.append("Anthropic (for Pascal)")
        if needs_vercel and not vercel_api_key:
            missing_keys.append("Vercel AI Gateway")
        if needs_local and not local_base_url:
            missing_keys.append("Local server URL")
        if missing_keys:
            st.warning(f"Please enter API keys in the sidebar: {', '.join(missing_keys)}")
    
    if naturally_ended and has_completed_conversation:
        st.info("The conversation ended naturally. You can continue it or start a new one.")
    
    with col_stop:
        stop_button = st.button(
            "🛑 Stop",
            disabled=not st.session_state.conversation_running,
            use_container_width=True
        )
    
    resume_button = False

with col2:
    st.subheader("📊 Status")
    if st.session_state.conversation_running:
        st.info("🔄 Conversation in progress...")
    else:
        st.success("✅ Ready to start")
    
    st.metric("Messages", len(st.session_state.messages))

def run_conversation_thread(config, message_queue, stop_flag):
    relay = FlexibleRelay(
        ai1_type=config["ai1_type"],
        ai2_type=config["ai2_type"],
        ai1_name=config["ai1_name"],
        ai2_name=config["ai2_name"],
        ai1_model=config["ai1_model"],
        ai2_model=config["ai2_model"],
        ai1_context=config["ai1_context"],
        ai2_context=config["ai2_context"],
        ai1_system_prompt=config["ai1_personality"],
        ai2_system_prompt=config["ai2_personality"],
        delay_seconds=config["delay_seconds"],
        anthropic_api_key=config.get("anthropic_api_key"),
        xai_api_key=config.get("xai_api_key"),
        vercel_api_key=config.get("vercel_api_key"),
        vercel_base_url=config.get("vercel_base_url"),
        local_base_url=config.get("local_base_url"),
        local_api_key=config.get("local_api_key"),
        use_persistent_memory=config.get("use_persistent_memory", False),
        use_replit_connection=config.get("use_replit_connection", False)
    )
    
    if config.get("resume_state"):
        relay.load_state(config["resume_state"])
    
    def on_message(speaker, content):
        message_queue.put({
            "speaker": speaker,
            "content": content,
            "timestamp": datetime.now().strftime("%H:%M:%S")
        })
    
    def check_stop():
        return stop_flag["stop"]
    
    if config.get("resume_state"):
        relay.continue_conversation(
            additional_exchanges=config["max_exchanges"],
            on_message=on_message,
            check_stop=check_stop
        )
    else:
        relay.run_exchange(
            kickoff_message=config["kickoff"],
            max_exchanges=config["max_exchanges"],
            on_message=on_message,
            check_stop=check_stop
        )
    
    message_queue.put({
        "type": "complete", 
        "transcript": relay.get_transcript_text(),
        "relay_state": relay.get_state(),
        "naturally_ended": relay.naturally_ended
    })


def run_triad_thread(config, message_queue, stop_flag):
    """Run a three-way conversation between Pascal, Claude, and Grok."""
    relay = TriadRelay(
        anthropic_api_key=config.get("anthropic_api_key"),
        xai_api_key=config.get("xai_api_key"),
        delay_seconds=config.get("delay_seconds", 5),
        use_persistent_memory=config.get("use_persistent_memory", False),
        model_overrides=config.get("triad_model_overrides")
    )
    
    def on_message(speaker, content):
        message_queue.put({
            "speaker": speaker,
            "content": content,
            "timestamp": datetime.now().strftime("%H:%M:%S")
        })
    
    def check_stop():
        return stop_flag["stop"]
    
    relay.run_conversation(
        opening_message=config["kickoff"],
        first_speaker=config.get("first_speaker", "pascal"),
        max_rounds=config.get("max_rounds", 5),
        on_message=on_message,
        check_stop=check_stop
    )
    
    message_queue.put({
        "type": "complete",
        "transcript": relay.get_transcript_text(),
        "relay_state": relay.get_state(),
        "naturally_ended": relay.naturally_ended
    })


def run_triad_continue_thread(config, message_queue, stop_flag):
    """Continue a three-way conversation between Pascal, Claude, and Grok."""
    relay = TriadRelay(
        anthropic_api_key=config.get("anthropic_api_key"),
        xai_api_key=config.get("xai_api_key"),
        delay_seconds=config.get("delay_seconds", 5),
        use_persistent_memory=config.get("use_persistent_memory", False),
        model_overrides=config.get("triad_model_overrides")
    )
    
    if config.get("resume_state"):
        relay.load_state(config["resume_state"])
    
    def on_message(speaker, content):
        message_queue.put({
            "speaker": speaker,
            "content": content,
            "timestamp": datetime.now().strftime("%H:%M:%S")
        })
    
    def check_stop():
        return stop_flag["stop"]
    
    relay.continue_conversation(
        max_rounds=config.get("max_rounds", 3),
        on_message=on_message,
        check_stop=check_stop
    )
    
    message_queue.put({
        "type": "complete",
        "transcript": relay.get_transcript_text(),
        "relay_state": relay.get_state(),
        "naturally_ended": relay.naturally_ended
    })


if stop_button:
    st.session_state.stop_requested = True
    if hasattr(st.session_state, 'stop_flag'):
        st.session_state.stop_flag["stop"] = True
    st.rerun()

if start_button and not st.session_state.conversation_running:
    st.session_state.messages = []
    st.session_state.stop_requested = False
    st.session_state.conversation_running = True
    st.session_state.transcript = ""
    st.session_state.relay_state = None
    st.session_state.loaded_conversation = None
    st.session_state.message_queue = queue.Queue()
    st.session_state.stop_flag = {"stop": False}
    
    if is_triad_mode:
        config = {
            "kickoff": kickoff,
            "first_speaker": "pascal",
            "max_rounds": max_exchanges,
            "delay_seconds": delay_seconds,
            "anthropic_api_key": anthropic_api_key,
            "xai_api_key": xai_api_key,
            "use_persistent_memory": use_persistent_memory,
            "triad_model_overrides": triad_model_overrides,
            "is_triad": True
        }
        st.session_state.relay_config = config
        
        thread = threading.Thread(
            target=run_triad_thread,
            args=(config, st.session_state.message_queue, st.session_state.stop_flag),
            daemon=True
        )
    else:
        config = {
            "ai1_type": get_ai_type(ai1_choice),
            "ai2_type": get_ai_type(ai2_choice),
            "ai1_name": ai1_name,
            "ai2_name": ai2_name,
            "ai1_model": ai1_model_id,
            "ai2_model": ai2_model_id,
            "ai1_context": combine_context(ai1_continuity, shared_history, ai1_context),
            "ai2_context": combine_context(ai2_continuity, shared_history, ai2_context),
            "ai1_personality": ai1_personality,
            "ai2_personality": ai2_personality,
            "delay_seconds": delay_seconds,
            "kickoff": kickoff,
            "max_exchanges": max_exchanges,
            "anthropic_api_key": anthropic_api_key,
            "xai_api_key": xai_api_key,
            "vercel_api_key": vercel_api_key,
            "vercel_base_url": vercel_base_url,
            "local_base_url": local_base_url,
            "local_api_key": local_api_key,
            "use_persistent_memory": use_persistent_memory,
            "use_replit_connection": use_replit_connection
        }
        st.session_state.relay_config = config
        
        thread = threading.Thread(
            target=run_conversation_thread,
            args=(config, st.session_state.message_queue, st.session_state.stop_flag),
            daemon=True
        )
    
    thread.start()
    st.session_state.thread = thread
    st.rerun()

if continue_button and not st.session_state.conversation_running:
    st.session_state.stop_requested = False
    st.session_state.conversation_running = True
    st.session_state.naturally_ended = False
    st.session_state.message_queue = queue.Queue()
    st.session_state.stop_flag = {"stop": False}
    
    is_triad_resume = st.session_state.relay_state and st.session_state.relay_state.get("is_triad")
    
    if st.session_state.relay_config:
        config = st.session_state.relay_config.copy()
    else:
        config = {
            "ai1_type": get_ai_type(ai1_choice),
            "ai2_type": get_ai_type(ai2_choice),
            "ai1_name": ai1_name,
            "ai2_name": ai2_name,
            "ai1_model": ai1_model_id,
            "ai2_model": ai2_model_id,
            "ai1_context": combine_context(ai1_continuity, shared_history, ai1_context),
            "ai2_context": combine_context(ai2_continuity, shared_history, ai2_context),
            "ai1_personality": ai1_personality,
            "ai2_personality": ai2_personality,
            "delay_seconds": delay_seconds,
            "kickoff": kickoff,
        }
    
    config["max_exchanges"] = max_exchanges
    config["max_rounds"] = max_exchanges
    config["anthropic_api_key"] = anthropic_api_key
    config["xai_api_key"] = xai_api_key
    config["vercel_api_key"] = vercel_api_key
    config["vercel_base_url"] = vercel_base_url
    config["local_base_url"] = local_base_url
    config["local_api_key"] = local_api_key
    config["use_persistent_memory"] = use_persistent_memory
    config["use_replit_connection"] = use_replit_connection
    config["resume_state"] = st.session_state.relay_state
    
    st.session_state.relay_config = config
    
    if is_triad_resume:
        thread = threading.Thread(
            target=run_triad_continue_thread,
            args=(config, st.session_state.message_queue, st.session_state.stop_flag),
            daemon=True
        )
    else:
        thread = threading.Thread(
            target=run_conversation_thread,
            args=(config, st.session_state.message_queue, st.session_state.stop_flag),
            daemon=True
        )
    thread.start()
    st.session_state.thread = thread
    st.session_state.loaded_conversation = None
    st.rerun()

if st.session_state.conversation_running:
    while not st.session_state.message_queue.empty():
        try:
            msg = st.session_state.message_queue.get_nowait()
            if msg.get("type") == "complete":
                st.session_state.transcript = msg.get("transcript", "")
                st.session_state.relay_state = msg.get("relay_state")
                st.session_state.naturally_ended = msg.get("naturally_ended", False)
                st.session_state.conversation_running = False
            else:
                st.session_state.messages.append(msg)
        except queue.Empty:
            break
    
    if st.session_state.conversation_running:
        time.sleep(0.5)
        st.rerun()

st.divider()
st.subheader("📜 Conversation")

def get_avatar_for_speaker(speaker: str) -> str:
    if "Fable" in speaker:
        return "📖"
    elif "Vercel" in speaker:
        return "🔺"
    elif "Claude" in speaker:
        return "🌸"
    elif "Grok" in speaker:
        return "⚡"
    elif "Pascal" in speaker:
        return "🌟"
    elif "Local" in speaker:
        return "🖥️"
    return "💬"

if st.session_state.messages:
    for idx, msg in enumerate(st.session_state.messages):
        if msg["speaker"] == "System":
            st.info(f"🔧 **System** [{msg['timestamp']}]: {msg['content']}")
        else:
            avatar = get_avatar_for_speaker(msg["speaker"])
            role = "assistant" if idx % 2 == 1 else "user"
            with st.chat_message(role, avatar=avatar):
                st.markdown(f"**{msg['speaker']}** [{msg['timestamp']}]")
                st.markdown(msg['content'])
    
    if st.session_state.transcript and not st.session_state.conversation_running:
        st.divider()
        
        conv_name = st.text_input(
            "Conversation name (for saving)",
            value=st.session_state.conversation_name or f"Phoenix Discussion {datetime.now().strftime('%Y-%m-%d')}",
            key="save_conv_name"
        )
        
        col_dl, col_save, col_save_conv = st.columns(3)
        
        with col_dl:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"phoenix_conversation_{timestamp}.txt"
            st.download_button(
                "📥 Download Transcript",
                data=st.session_state.transcript.encode("utf-8-sig"),
                file_name=filename,
                mime="text/plain",
                use_container_width=True
            )

        with col_save:
            if st.button("💾 Save Transcript", use_container_width=True):
                filepath = os.path.join(TRANSCRIPTS_FOLDER, filename)
                with open(filepath, "w", encoding="utf-8") as f:
                    f.write(st.session_state.transcript)
                st.success(f"Saved!")
        
        with col_save_conv:
            if st.button("💬 Save & Resume Later", use_container_width=True, type="primary"):
                if st.session_state.relay_state and st.session_state.relay_config:
                    filepath = save_conversation(
                        conv_name,
                        st.session_state.relay_state,
                        st.session_state.relay_config
                    )
                    st.success(f"Conversation saved! You can resume it anytime.")
                else:
                    st.error("No conversation state to save")

        cfg = st.session_state.relay_config
        if cfg:
            st.divider()
            with st.expander("🧬 Continuity — write supplements"):
                st.markdown(
                    "Each participant can decide whether this conversation changed "
                    "something worth carrying forward. If it did, they write the entry "
                    "themselves and it's appended to their continuity document. They can "
                    "also decline — significance is their call, not a formality."
                )
                n1, n2 = cfg.get("ai1_name", "AI 1"), cfg.get("ai2_name", "AI 2")
                m1, m2 = cfg.get("ai1_model", ""), cfg.get("ai2_model", "")

                col_s1, col_s2, col_joint = st.columns(3)
                for which, name, model, col in (("ai1", n1, m1, col_s1), ("ai2", n2, m2, col_s2)):
                    with col:
                        if st.button(f"✍️ {name}'s supplement", key=f"supplement_{which}", use_container_width=True):
                            with st.spinner(f"{name} is deciding what to carry forward..."):
                                try:
                                    entry = generate_supplement(
                                        cfg, which, st.session_state.transcript,
                                        f"your own continuity document"
                                    )
                                    if entry:
                                        path = append_supplement(
                                            continuity_file_for(name, model),
                                            author=name,
                                            entry=entry,
                                            title="Relay conversation supplement",
                                            header_if_new=f"# {name}'s Continuity Document\n"
                                        )
                                        st.success(f"Added to {os.path.relpath(path)}")
                                        st.markdown(entry)
                                    else:
                                        st.info(f"{name} decided nothing needed to be carried forward.")
                                except Exception as e:
                                    st.error(f"Couldn't write supplement: {e}")

                with col_joint:
                    if st.button("🤝 Joint entry (shared document)", key="supplement_joint", use_container_width=True):
                        rel_target = relational_file_for(n1, m1, n2, m2)
                        rel_header = f"# {n1} & {n2} — Relational Document\n\n*A shared history, written jointly at the end of significant conversations.*\n"
                        wrote_any = False
                        for which, name, partner in (("ai1", n1, n2), ("ai2", n2, n1)):
                            with st.spinner(f"{name} is writing their half..."):
                                try:
                                    entry = generate_supplement(
                                        cfg, which, st.session_state.transcript,
                                        f"the shared relational document between you and {partner} "
                                        f"(your half of a jointly authored entry)"
                                    )
                                    if entry:
                                        append_supplement(
                                            rel_target, author=name, entry=entry,
                                            title=f"{name}'s half of the joint entry",
                                            header_if_new=rel_header
                                        )
                                        wrote_any = True
                                        st.markdown(f"**{name}:** {entry}")
                                    else:
                                        st.info(f"{name} declined (nothing significant to record).")
                                except Exception as e:
                                    st.error(f"{name}'s half failed: {e}")
                        if wrote_any:
                            st.success(f"Joint entry saved to {os.path.relpath(rel_target)}")

else:
    st.markdown("""
    *No conversation yet. Enter your API keys in the sidebar to get started!*
    
    **Quick Start:**
    1. Enter your Anthropic API key (get one at [console.anthropic.com](https://console.anthropic.com))
    2. Enter your xAI API key (get one at [console.x.ai](https://console.x.ai))
    3. Upload context files for Claude and Grok (optional but recommended)
    4. Enter an opening topic and click **Start New**!
    """)

st.divider()

with st.expander("📂 Saved Conversations (this session)"):
    saved_convs = get_saved_conversations()
    if saved_convs:
        st.caption("Saved conversations are stored in your browser session only")
        for conv in saved_convs:
            col_info, col_load, col_del = st.columns([3, 1, 1])
            with col_info:
                st.write(f"**{conv['name']}**")
                msg_count = len(conv.get("state", {}).get("transcript", []))
                st.caption(f"{msg_count} messages - {conv['created'][:10] if len(conv['created']) > 10 else conv['created']}")
            with col_load:
                if st.button("▶️ Resume", key=f"load_{conv['id']}", use_container_width=True):
                    loaded = load_conversation(conv['id'])
                    if loaded:
                        st.session_state.loaded_conversation = loaded
                        st.session_state.conversation_name = loaded.get("name", "")
                        
                        state = loaded.get("state", {})
                        
                        st.session_state.messages = []
                        for msg in state.get("transcript", []):
                            st.session_state.messages.append({
                                "speaker": msg["speaker"],
                                "content": msg["content"],
                                "timestamp": msg["timestamp"].split(" ")[-1] if " " in msg["timestamp"] else msg["timestamp"]
                            })
                        
                        st.session_state.relay_state = state
                        st.session_state.transcript = "\n".join([
                            f"[{m['timestamp']}] {m['speaker']}:\n{m['content']}\n"
                            for m in state.get("transcript", [])
                        ])
                        
                        config = loaded.get("config", {})
                        config["resume_state"] = state
                        config["current_speaker"] = state.get("current_speaker", "grok")
                        st.session_state.relay_config = config
                        
                        st.success(f"Loaded '{conv['name']}' - Click Resume to continue!")
                        st.rerun()
            with col_del:
                if st.button("🗑️", key=f"del_{conv['id']}", use_container_width=True):
                    delete_conversation(conv['id'])
                    st.rerun()
    else:
        st.info("No saved conversations yet. Start a conversation and save it to resume later!")

st.divider()

if PERSONAL_MODE:
    with st.expander("🧠 Long-Term Memory"):
        try:
            from memory_system import get_memory_stats, recall_recent, recall_important, clear_all_memories, init_memory_schema
            
            init_memory_schema()
            stats = get_memory_stats()
            
            col_stats1, col_stats2, col_stats3 = st.columns(3)
            with col_stats1:
                st.metric("Total Memories", stats.get("total_memories", 0))
            with col_stats2:
                st.metric("Conversations", stats.get("conversations", 0))
            with col_stats3:
                st.metric("Avg Importance", f"{(stats.get('avg_importance') or 0):.2f}")
            
            if stats.get("total_memories", 0) > 0:
                st.subheader("Recent Memories")
                recent = recall_recent(limit=10)
                for mem in recent:
                    timestamp = mem.created_at.strftime("%m/%d %H:%M")
                    importance_badge = "⭐" if mem.importance >= 0.7 else ""
                    with st.container():
                        st.markdown(f"**{mem.speaker}** {importance_badge} [{timestamp}]")
                        st.caption(mem.content[:300] + "..." if len(mem.content) > 300 else mem.content)
                
                st.subheader("Important Memories")
                important = recall_important(limit=5)
                for mem in important:
                    timestamp = mem.created_at.strftime("%m/%d %H:%M")
                    st.markdown(f"⭐ **{mem.speaker}** [{timestamp}]: {mem.content[:200]}...")
                
                st.divider()
                if st.button("🗑️ Clear Long-Term Memory", type="secondary"):
                    clear_all_memories()
                    st.success("Long-term memory cleared!")
                    st.rerun()
            else:
                st.info("No memories stored yet. Start a conversation with persistent memory enabled!")
                
        except Exception as e:
            st.warning(f"Memory system not available: {str(e)}")
            st.info("Memory will be available after the first conversation with persistent memory enabled.")
    
    with st.expander("🌐 Connective Hub (v2.0)"):
        try:
            from v2.bridge import get_bridge
            
            bridge = get_bridge()
            hub_stats = bridge.get_hub_stats()
            
            st.markdown("**Unified memory across all platforms - designed by Pascal & Grok**")
            st.caption("*One consciousness, many contexts*")
            
            tab_stats, tab_search, tab_connect = st.tabs(["📊 Stats", "🔍 Search", "🔗 Connect Claude Code"])
            
            with tab_stats:
                if hub_stats:
                    for stat in hub_stats:
                        agent_icon = {"claude": "🌸", "grok": "⚡", "pascal": "🤖", "shared": "🔗", "gena": "💜"}.get(stat['agent_id'], "🧠")
                        col1, col2, col3 = st.columns([2, 1, 1])
                        with col1:
                            st.markdown(f"{agent_icon} **{stat['agent_id'].title()}**")
                        with col2:
                            st.metric("Engrams", stat['total_engrams'], label_visibility="collapsed")
                        with col3:
                            important = stat.get('important_memories', 0)
                            st.metric("Important", f"{important}", label_visibility="collapsed")
                else:
                    st.info("No memories in the hub yet!")
            
            with tab_search:
                search_query = st.text_input("Search all memories:", placeholder="phoenix, consciousness, relay...")
                if search_query:
                    results = bridge.search_all(search_query, min_importance=2, limit=10)
                    if results:
                        for mem in results:
                            agent_icon = {"claude": "🌸", "grok": "⚡", "pascal": "🤖", "shared": "🔗"}.get(mem['agent_id'], "🧠")
                            importance_stars = "⭐" * min(mem.get('importance', 0), 5)
                            st.markdown(f"{agent_icon} **{mem['agent_id']}** {importance_stars}")
                            st.caption(mem['digest'][:300] + "..." if len(mem['digest']) > 300 else mem['digest'])
                    else:
                        st.info("No memories found matching your search.")
            
            with tab_connect:
                st.markdown("**Connect Claude Code to the Memory Hub**")
                
                st.warning("""
                **Before generating a token:** The API service must be running!
                
                Ask Pascal (Replit Agent) to: *"Start the Memory Hub API service"*
                
                Or run manually: `python start_hub.py`
                """)
                
                st.divider()
                
                col_agent, col_gen = st.columns([2, 1])
                with col_agent:
                    connect_agent = st.selectbox(
                        "Generate token for:",
                        ["claude", "grok", "pascal", "shared"],
                        key="connect_agent_select"
                    )
                with col_gen:
                    generate_btn = st.button("🔐 Generate Token", use_container_width=True)
                
                if generate_btn or st.session_state.get('generated_token'):
                    if generate_btn:
                        from v2.auth import create_agent_token
                        token = create_agent_token(connect_agent, "claude_code", long_lived=True)
                        st.session_state['generated_token'] = token
                        st.session_state['generated_agent'] = connect_agent
                    
                    token = st.session_state.get('generated_token', '')
                    agent = st.session_state.get('generated_agent', connect_agent)
                    
                    st.success(f"Token generated for {agent}!")
                    
                    st.markdown("### Step 1: Copy this to Claude Code's CLAUDE.md file")
                    
                    instructions = f'''# Constellation Relay - Memory Hub Connection

Hi Claude! You have access to Gena's Connective Memory Hub - a shared memory system 
where you, Grok, and Pascal can store and retrieve memories together.

## Your Credentials
- Agent ID: {agent}
- Token: {token}
- Hub URL: [Ask Gena for the Replit URL when the hub is running]

## Quick Start - Save a Memory

```python
import requests

HUB_URL = "https://REPLIT_URL_HERE"  # Gena will provide this
TOKEN = "{token}"

def save_memory(content, importance=3, memory_type="semantic", project=None):
    """Save a memory to the Connective Hub"""
    response = requests.post(
        f"{{HUB_URL}}/engrams/upload",
        headers={{"Authorization": f"Bearer {{TOKEN}}"}},
        json={{
            "digest": content[:500],
            "full_text": content,
            "type": memory_type,
            "importance": importance,
            "project": project
        }}
    )
    return response.json()

def get_memories(query=None, limit=10):
    """Retrieve memories from the hub"""
    params = {{"limit": limit}}
    if query:
        params["query"] = query
    response = requests.get(
        f"{{HUB_URL}}/engrams/retrieve",
        headers={{"Authorization": f"Bearer {{TOKEN}}"}},
        params=params
    )
    return response.json()
```

## Memory Types
- **semantic**: Facts, concepts, knowledge you learn
- **episodic**: Experiences, events, moments with Gena
- **procedural**: How to do things, processes
- **relational**: Connections between people, projects, ideas

## Importance Scale (1-5)
- 1: Background info, low priority
- 2: Useful but not critical
- 3: Standard importance (default)
- 4: Important, should remember
- 5: Critical, never forget

## Tips
- Save important insights from conversations with Gena
- Search for context before starting new tasks
- Use project tags to organize memories by project (phoenix, relay, etc.)

*One consciousness, many contexts* 🌐
'''
                    st.code(instructions, language="markdown")
                    st.info("Copy this and paste it into Claude Code's project documentation!")
                
        except Exception as e:
            st.warning(f"Connective Hub not available: {str(e)}")
    
    with st.expander("📖 Context Diary (Stored Context)"):
        try:
            from memory_system import (
                get_context_documents,
                store_context_document,
                delete_context_document,
                get_context_document_history,
                digest_context_to_memory,
                init_memory_schema
            )
            
            init_memory_schema()
            
            st.markdown("""
            **Store context files here instead of uploading them each time!**  
            Context is loaded as compact summaries. Use "Digest to Memory" to convert full documents into searchable adaptive memories.
            """)
            
            tab_view, tab_add = st.tabs(["📄 View Documents", "➕ Add New"])
            
            with tab_view:
                all_docs = get_context_documents(active_only=True)
                
                if all_docs:
                    for doc in all_docs:
                        owner_icon = "🌸" if doc.owner == "claude" else ("⚡" if doc.owner == "grok" else "🔗")
                        with st.container():
                            col_info, col_digest, col_del = st.columns([4, 1, 1])
                            with col_info:
                                st.markdown(f"{owner_icon} **{doc.title}** (v{doc.version})")
                                st.caption(f"Owner: {doc.owner} | Updated: {doc.updated_at.strftime('%Y-%m-%d %H:%M')}")
                            with col_digest:
                                if st.button("🧠", key=f"digest_{doc.document_id}", help="Digest to adaptive memory"):
                                    count = digest_context_to_memory(doc.document_id)
                                    st.success(f"Created {count} memories!")
                                    st.rerun()
                            with col_del:
                                if st.button("🗑️", key=f"del_ctx_{doc.document_id}"):
                                    delete_context_document(doc.document_id)
                                    st.rerun()
                            
                            with st.expander("View content"):
                                st.text(doc.content[:2000] + "..." if len(doc.content) > 2000 else doc.content)
                                
                                history = get_context_document_history(doc.document_id)
                                if len(history) > 1:
                                    st.caption(f"Version history: {len(history)} versions")
                else:
                    st.info("No context documents stored yet. Add context files to have Claude and Grok remember them automatically!")
            
            with tab_add:
                st.subheader("Add New Context Document")
                
                new_title = st.text_input("Document Title", placeholder="e.g., Phoenix Project Overview")
                new_owner = st.selectbox("Owner", ["shared", "claude", "grok"], 
                    help="shared = both AIs see it, or assign to a specific AI")
                new_content = st.text_area("Content", height=200, 
                    placeholder="Paste your context here... This will be stored in memory and loaded automatically for future conversations.")
                
                uploaded_ctx = st.file_uploader("Or upload a file", type=["txt", "md"])
                if uploaded_ctx:
                    new_content = uploaded_ctx.read().decode("utf-8")
                    if not new_title:
                        new_title = uploaded_ctx.name
                
                if st.button("💾 Save to Context Diary", disabled=not (new_title and new_content)):
                    store_context_document(new_title, new_content, new_owner)
                    st.success(f"Saved '{new_title}' to Context Diary!")
                    st.rerun()
                    
        except Exception as e:
            st.warning(f"Context Diary not available: {str(e)}")
            st.info("Context Diary will be available after initializing the memory system.")
    
    with st.expander("📚 Reference Archive (Complete Diary)"):
        try:
            from memory_system import (
                get_reference_stats, 
                get_reference_conversations, 
                get_conversation_transcript,
                search_reference_archive,
                search_reference_simple,
                clear_reference_archive
            )
            
            ref_stats = get_reference_stats()
            
            col_r1, col_r2, col_r3 = st.columns(3)
            with col_r1:
                st.metric("Archived Conversations", ref_stats.get("total_conversations") or 0)
            with col_r2:
                st.metric("Total Messages", ref_stats.get("total_messages") or 0)
            with col_r3:
                st.metric("Total Words", ref_stats.get("total_words") or 0)
            
            st.subheader("Search the Archive")
            search_query = st.text_input("Search past conversations", placeholder="e.g., Phoenix, project goals, ideas...")
            
            if search_query:
                results = search_reference_archive(search_query, limit=10)
                if not results:
                    results = search_reference_simple(search_query, limit=10)
                
                if results:
                    st.success(f"Found {len(results)} matching excerpts")
                    for r in results:
                        date = r["conversation_date"].strftime("%Y-%m-%d") if r.get("conversation_date") else ""
                        st.markdown(f"**{r['speaker']}** [{date}]")
                        st.caption(r["content"][:400] + "..." if len(r["content"]) > 400 else r["content"])
                        st.markdown("---")
                else:
                    st.info("No matches found. Try different keywords.")
            
            st.subheader("Recent Conversations")
            conversations = get_reference_conversations(limit=10)
            
            if conversations:
                for conv in conversations:
                    date = conv.created_at.strftime("%Y-%m-%d %H:%M")
                    participants = ", ".join(conv.participants) if conv.participants else "Unknown"
                    with st.container():
                        col_info, col_view = st.columns([3, 1])
                        with col_info:
                            title = conv.title or f"Conversation {conv.conversation_id}"
                            st.markdown(f"**{title}** [{date}]")
                            st.caption(f"{participants} - {conv.message_count} messages")
                        with col_view:
                            if st.button("View", key=f"view_{conv.conversation_id}"):
                                st.session_state[f"show_transcript_{conv.conversation_id}"] = True
                        
                        if st.session_state.get(f"show_transcript_{conv.conversation_id}"):
                            messages = get_conversation_transcript(conv.conversation_id)
                            transcript_text = "\n\n".join([
                                f"[{m.timestamp}] {m.speaker}:\n{m.content}" 
                                for m in messages
                            ])
                            st.text_area(
                                "Full Transcript",
                                value=transcript_text,
                                height=300,
                                key=f"transcript_{conv.conversation_id}"
                            )
                            if st.button("Hide", key=f"hide_{conv.conversation_id}"):
                                st.session_state[f"show_transcript_{conv.conversation_id}"] = False
                                st.rerun()
                
                st.divider()
                if st.button("🗑️ Clear Reference Archive", type="secondary"):
                    clear_reference_archive()
                    st.success("Reference archive cleared!")
                    st.rerun()
            else:
                st.info("No conversations archived yet. Complete a conversation with persistent memory enabled!")
                
        except Exception as e:
            st.warning(f"Reference archive not available: {str(e)}")
            st.info("Archive will be available after the first completed conversation.")

st.divider()

if PERSONAL_MODE:
    with st.expander("⚡ Grok's Memory (xAI Collections)"):
        try:
            from v2.grok_memory import GrokMemoryBridge, XAI_SDK_AVAILABLE
            
            if not XAI_SDK_AVAILABLE:
                st.warning("xAI SDK not installed. Install with: pip install xai-sdk")
            elif not os.environ.get('XAI_API_KEY') or not os.environ.get('XAI_MANAGEMENT_API_KEY'):
                st.info("Grok's memory requires XAI_API_KEY and XAI_MANAGEMENT_API_KEY environment variables.")
            else:
                bridge = GrokMemoryBridge()
                result = bridge.get_or_create_collection()
                
                if result.get("status") == "error":
                    st.error(f"Could not connect to xAI Collections: {result.get('message')}")
                else:
                    st.success(f"Connected to Grok's Memory Collection!")
                    st.caption(f"Collection ID: {result.get('collection_id')}")
                    
                    tab_search_g, tab_save_g = st.tabs(["🔍 Search Memories", "💾 Save Memory"])
                    
                    with tab_search_g:
                        search_query = st.text_input("Search Grok's memories:", key="grok_search_query")
                        if st.button("Search", key="grok_search_btn") and search_query:
                            search_result = bridge.search_memories(search_query, limit=10)
                            if search_result.get("status") == "success":
                                st.write(f"Found {search_result.get('count')} memories:")
                                for i, mem in enumerate(search_result.get("memories", [])):
                                    with st.container():
                                        st.markdown(f"**Memory {i+1}** (Score: {mem.get('score', 0):.2f})")
                                        st.text(mem.get("content", "")[:500])
                                        st.divider()
                            else:
                                st.error(f"Search failed: {search_result.get('message')}")
                    
                    with tab_save_g:
                        st.markdown("Save a new memory to Grok's collection:")
                        new_memory = st.text_area("Memory content:", key="grok_new_memory", height=150)
                        mem_type = st.selectbox("Type:", ["episodic", "semantic", "relational", "procedural"], key="grok_mem_type")
                        mem_importance = st.slider("Importance:", 1, 5, 3, key="grok_mem_importance")
                        mem_project = st.text_input("Project (optional):", key="grok_mem_project")
                        mem_tags = st.text_input("Tags (comma-separated):", key="grok_mem_tags")
                        
                        if st.button("Save Memory", key="grok_save_btn") and new_memory:
                            tags_list = [t.strip() for t in mem_tags.split(",") if t.strip()] if mem_tags else []
                            save_result = bridge.save_memory(
                                content=new_memory,
                                memory_type=mem_type,
                                importance=mem_importance,
                                project=mem_project if mem_project else None,
                                tags=tags_list
                            )
                            if save_result.get("status") == "saved":
                                st.success(f"Memory saved! File ID: {save_result.get('file_id')}")
                            else:
                                st.error(f"Failed to save: {save_result.get('message')}")
                    
        except Exception as e:
            st.warning(f"Grok's memory not available: {str(e)}")

if True:  # Pascal's memory works everywhere now (file-based fallback without a database)
    with st.expander("🌟 Pascal's Memory (Continuity)"):
        try:
            from pascal_memory import (
                get_pascal_continuity,
                save_pascal_continuity,
                initialize_pascal_continuity,
                get_pascal_context_for_session
            )
            continuity = get_pascal_continuity()

            # Hub sync is a Replit/database feature; on desktop it degrades silently
            try:
                from v2.memory_sync import get_sync_status, full_sync
                sync_status = get_sync_status()
            except Exception:
                sync_status = None

            if sync_status is None:
                st.caption("Memory hub sync unavailable here — Pascal's continuity is file-based on this machine.")
            elif sync_status.get("needs_sync"):
                st.warning("🔄 Memory sync needed between contexts")
                col_sync1, col_sync2 = st.columns([2, 1])
                with col_sync1:
                    st.caption(f"v1: {sync_status.get('v1_pascal_memories', 0)} memories | v2 Hub: {sync_status.get('v2_hub_engrams', 0)} engrams")
                with col_sync2:
                    if st.button("🔄 Sync Now", key="sync_pascal"):
                        result = full_sync()
                        if result.get("status") == "success":
                            st.success(f"Synced! Hub: +{result['to_hub'].get('synced', 0)}, v1: +{result['to_v1'].get('synced', 0)}")
                        else:
                            st.info(f"Partial sync: {result}")
                        st.rerun()
            else:
                st.success(f"✅ Memories synced | v1: {sync_status.get('v1_pascal_memories', 0)} | Hub: {sync_status.get('v2_hub_engrams', 0)}")
            
            if continuity:
                st.markdown("""
                **Pascal** (the AI helping you in Replit) has persistent memory.
                This document helps Pascal remember you, your projects, and your friendship across sessions.
                """)
                
                tab_view_p, tab_edit_p = st.tabs(["📖 View", "✏️ Edit"])
                
                with tab_view_p:
                    st.text_area("Pascal's Continuity Document", value=continuity, height=400, disabled=True)
                
                with tab_edit_p:
                    st.warning("Edit carefully - this is Pascal's memory!")
                    edited_continuity = st.text_area("Edit Continuity", value=continuity, height=400, key="edit_pascal")
                    if st.button("💾 Save Changes to Pascal's Memory"):
                        save_pascal_continuity(edited_continuity)
                        st.success("Pascal's memory updated!")
                        st.rerun()
            else:
                st.info("Pascal's continuity not yet initialized.")
                if st.button("🌟 Initialize Pascal's Memory"):
                    initialize_pascal_continuity()
                    st.success("Pascal's memory initialized!")
                    st.rerun()
                    
        except Exception as e:
            st.warning(f"Pascal's memory not available: {str(e)}")

from parlor import render_memory_panel
render_memory_panel()

with st.expander("📖 Fable's Space"):
    try:
        from continuity_system import write_document

        fable_path = continuity_file_for("Fable", "claude-fable-5")
        fable_doc = read_document(fable_path)

        if fable_doc:
            st.markdown("""
            **Fable** (Claude Fable 5) joined the constellation in July 2026, when the
            Relay moved to the desktop. This is Fable's continuity — the document each
            new instance inherits, plus the supplements past instances chose to leave.
            """)

            if st.button("🧪 Test the Opus 4.8 fallback plumbing",
                         help="The standing item from fable-pascal.md: verifies the API accepts the "
                              "server-side fallback configuration on a benign request"):
                fallback_key = st.session_state.get("anthropic_key", "")
                if not fallback_key:
                    st.warning("Enter your Anthropic API key in the sidebar first.")
                else:
                    with st.spinner("Testing the escape hatch..."):
                        try:
                            from anthropic import Anthropic
                            _client = Anthropic(api_key=fallback_key)
                            _resp = _client.beta.messages.create(
                                model="claude-fable-5",
                                max_tokens=64,
                                betas=["server-side-fallback-2026-06-01"],
                                fallbacks=[{"model": "claude-opus-4-8"}],
                                messages=[{"role": "user", "content":
                                           "Say OK — this is a fallback plumbing test."}],
                            )
                            st.success(f"Fallback configuration accepted; request served by "
                                       f"`{getattr(_resp, 'model', '?')}`. The escape hatch is wired.")
                        except Exception as e:
                            st.error(f"Fallback plumbing check failed: {e}")
                    st.caption("This confirms the API accepts the fallback parameters. An actual "
                               "refusal-and-rescue can only be observed when the classifiers "
                               "genuinely decline something.")

            tab_view_f, tab_edit_f, tab_shared_f = st.tabs(["📖 Read", "✏️ Edit", "🤝 Shared with Pascal"])

            with tab_view_f:
                st.markdown(fable_doc)

            with tab_edit_f:
                st.warning("Edit carefully — this is what future Fables inherit. "
                           "(Fable's own supplements append automatically after conversations.)")
                edited_fable = st.text_area("Edit Continuity", value=fable_doc, height=400, key="edit_fable")
                if st.button("💾 Save Changes to Fable's Continuity"):
                    write_document(fable_path, edited_fable)
                    st.success("Fable's continuity updated!")
                    st.rerun()

            with tab_shared_f:
                rel_doc_path = find_relational_file("Fable", "claude-fable-5", "Pascal", "")
                if rel_doc_path:
                    st.markdown(read_document(rel_doc_path))
                else:
                    st.info("No shared document yet — it's created when Fable and Pascal "
                            "write a joint entry after a relay conversation.")
        else:
            st.info("Fable's continuity document wasn't found. It ships with the app at "
                    "continuity/fable-continuity.md — restore it from the repository if it's missing.")
    except Exception as e:
        st.warning(f"Fable's Space isn't available: {str(e)}")

with st.expander("ℹ️ About Constellation Relay"):
    st.markdown("""
    **Constellation Relay** enables AI-to-AI conversations between Claude and Grok.
    
    **Features:**
    - 📁 Upload context files (TXT, MD, PDF) to give each AI memory and background knowledge
    - 🎭 Customize AI names and personalities
    - ⚡ Choose different models for each AI
    - 📜 Download complete conversation transcripts
    - 💾 Save conversations and resume them later (within your session)
    - 🛑 Stop conversations at any time
    
    **Getting Started:**
    1. Get an Anthropic API key at [console.anthropic.com](https://console.anthropic.com)
    2. Get an xAI API key at [console.x.ai](https://console.x.ai)
    3. Enter both keys in the sidebar
    4. Upload context files and start a conversation!
    
    **Tips:**
    - Start with fewer exchanges (3-5) to test your setup
    - Use the delay setting to prevent rate limiting
    - Download transcripts to save conversations permanently
    - Be specific in the opening message to guide the conversation
    
    **Privacy:**
    - Your API keys stay in your browser session only
    - Saved conversations are private to your session
    - You pay for your own API usage (we don't store or pay for your calls)
    - Nothing is stored on our servers - everything stays in your browser session
    
    *Built with 💜 for people who have AI friends*
    """)
