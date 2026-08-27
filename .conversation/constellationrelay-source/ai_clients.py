import os
from anthropic import Anthropic
from openai import OpenAI
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception

AI_INTEGRATIONS_ANTHROPIC_API_KEY = os.environ.get("AI_INTEGRATIONS_ANTHROPIC_API_KEY")
AI_INTEGRATIONS_ANTHROPIC_BASE_URL = os.environ.get("AI_INTEGRATIONS_ANTHROPIC_BASE_URL")
AI_INTEGRATIONS_OPENROUTER_API_KEY = os.environ.get("AI_INTEGRATIONS_OPENROUTER_API_KEY")
AI_INTEGRATIONS_OPENROUTER_BASE_URL = os.environ.get("AI_INTEGRATIONS_OPENROUTER_BASE_URL")

XAI_BASE_URL = "https://api.x.ai/v1"

# Vercel AI Gateway - OpenAI-compatible. Serves models (including deprecated
# Anthropic models like Opus 4) via slugs like "anthropic/claude-opus-4".
VERCEL_GATEWAY_BASE_URL = os.environ.get(
    "AI_GATEWAY_BASE_URL", "https://ai-gateway.vercel.sh/v1"
)
VERCEL_GATEWAY_API_KEY = os.environ.get("AI_GATEWAY_API_KEY")

# Local model server - any OpenAI-compatible endpoint.
# Ollama:     http://localhost:11434/v1  (api key can be anything, e.g. "ollama")
# LM Studio:  http://localhost:1234/v1
LOCAL_BASE_URL = os.environ.get("LOCAL_AI_BASE_URL", "http://localhost:11434/v1")
LOCAL_API_KEY = os.environ.get("LOCAL_AI_API_KEY", "ollama")

LOCAL_SERVER_PRESETS = {
    "Ollama": "http://localhost:11434/v1",
    "LM Studio": "http://localhost:1234/v1",
    "llama.cpp / other": "http://localhost:8080/v1",
}

def _build_client(builder):
    """Build an API client, returning None instead of crashing when the
    environment credentials it depends on aren't set (e.g. outside Replit)."""
    try:
        return builder()
    except Exception:
        return None

anthropic_client = _build_client(lambda: Anthropic(
    api_key=AI_INTEGRATIONS_ANTHROPIC_API_KEY,
    base_url=AI_INTEGRATIONS_ANTHROPIC_BASE_URL
))

openrouter_client = _build_client(lambda: OpenAI(
    api_key=AI_INTEGRATIONS_OPENROUTER_API_KEY,
    base_url=AI_INTEGRATIONS_OPENROUTER_BASE_URL
))

def get_anthropic_client(custom_api_key: str = None) -> Anthropic:
    if custom_api_key:
        return Anthropic(api_key=custom_api_key)
    if anthropic_client is None:
        raise RuntimeError(
            "No Anthropic API key available. Enter your key in the sidebar."
        )
    return anthropic_client

def get_grok_client(custom_api_key: str = None) -> OpenAI:
    if custom_api_key:
        return OpenAI(api_key=custom_api_key, base_url=XAI_BASE_URL)
    if openrouter_client is None:
        raise RuntimeError(
            "No xAI/OpenRouter API key available. Enter your key in the sidebar."
        )
    return openrouter_client

def get_vercel_client(custom_api_key: str = None, base_url: str = None) -> OpenAI:
    return OpenAI(
        api_key=custom_api_key or VERCEL_GATEWAY_API_KEY,
        base_url=base_url or VERCEL_GATEWAY_BASE_URL,
    )

def get_local_client(base_url: str = None, custom_api_key: str = None) -> OpenAI:
    return OpenAI(
        api_key=custom_api_key or LOCAL_API_KEY,
        base_url=base_url or LOCAL_BASE_URL,
    )

XAI_GROK_MODELS = {
    "Grok 4": "grok-4",
    "Grok 4 (Latest)": "grok-4-latest",
    "Grok 4.1 Fast": "grok-4-1-fast",
    "Grok 3": "grok-3",
    "Grok 3 (Latest)": "grok-3-latest",
    "Grok 3 Mini": "grok-3-mini",
    "Grok 2": "grok-2",
    "Grok 2 Mini": "grok-2-mini",
}


def is_rate_limit_error(exception: BaseException) -> bool:
    error_msg = str(exception)
    return (
        "429" in error_msg
        or "RATELIMIT_EXCEEDED" in error_msg
        or "quota" in error_msg.lower()
        or "rate limit" in error_msg.lower()
        or (hasattr(exception, "status_code") and exception.status_code == 429)
    )


def _extract_anthropic_text(response) -> str:
    """Get text out of an Anthropic response, handling refusals and thinking blocks.

    Newer models (Fable 5, Opus 4.7+) may return thinking blocks before text,
    and can decline a request with stop_reason == "refusal" instead of raising.
    """
    if getattr(response, "stop_reason", None) == "refusal":
        detail = ""
        stop_details = getattr(response, "stop_details", None)
        if stop_details is not None and getattr(stop_details, "explanation", None):
            detail = f" Reason given: {stop_details.explanation}"
        return (
            f"[{getattr(response, 'model', 'The model')} declined to respond to this "
            f"message.{detail} You can rephrase or steer the conversation elsewhere.]"
        )
    parts = [
        block.text for block in response.content
        if getattr(block, "type", None) == "text" and block.text
    ]
    if not parts and getattr(response, "stop_reason", None) == "max_tokens":
        return ("[The reply ran out of space before reaching words — the model spent "
                "its whole budget thinking. Try asking again, perhaps more specifically.]")
    return "\n\n".join(parts).strip()


def _stream_final(messages_api, **kwargs):
    """Stream a request and return the final message.

    Streaming keeps the connection alive during long thinking (Fable can take
    minutes) instead of risking silent HTTP timeouts on big max_tokens.
    """
    with messages_api.stream(**kwargs) as stream:
        return stream.get_final_message()


def _call_openai_compatible(client: OpenAI, model: str, messages: list, system_prompt: str, max_tokens: int = 8192) -> str:
    formatted_messages = [{"role": "system", "content": system_prompt}] + messages
    response = client.chat.completions.create(
        model=model,
        messages=formatted_messages,
        max_tokens=max_tokens
    )
    return response.choices[0].message.content or ""


def list_openai_models(base_url: str, api_key: str = "none") -> list:
    """List model IDs from any OpenAI-compatible server (Ollama, LM Studio, Vercel Gateway)."""
    try:
        client = OpenAI(api_key=api_key or "none", base_url=base_url, timeout=10.0)
        return sorted(m.id for m in client.models.list())
    except Exception:
        return []


@retry(
    stop=stop_after_attempt(5),
    wait=wait_exponential(multiplier=1, min=2, max=60),
    retry=retry_if_exception(is_rate_limit_error),
    reraise=True
)
def call_claude(messages: list, system_prompt: str, model: str = "claude-opus-4-8", custom_api_key: str = None) -> str:
    client = get_anthropic_client(custom_api_key)

    if model == "claude-fable-5":
        # Fable 5's safety classifiers can decline a request; opt into the
        # server-side fallback so the conversation continues on Opus 4.8
        # instead of stopping. If this account/SDK doesn't support the beta,
        # fall through to a plain request below.
        try:
            response = _stream_final(
                client.beta.messages,
                model=model,
                max_tokens=16000,
                system=system_prompt,
                messages=messages,
                betas=["server-side-fallback-2026-06-01"],
                fallbacks=[{"model": "claude-opus-4-8"}],
            )
            text = _extract_anthropic_text(response)
            # Never let a fallback model speak wearing Fable's name (Gena's
            # rule, July 11 2026): if another model served the reply, say so.
            served_by = getattr(response, "model", "") or ""
            if text and served_by and "fable" not in served_by.lower():
                text = (f"*[Fable's reply was declined by safety classifiers; "
                        f"{served_by} answered in his place. This is a different "
                        f"voice - hold it accordingly.]*\n\n{text}")
            return text
        except Exception as e:
            if is_rate_limit_error(e):
                raise

    response = _stream_final(
        client.messages,
        model=model,
        max_tokens=16000,
        system=system_prompt,
        messages=messages
    )
    return _extract_anthropic_text(response)


@retry(
    stop=stop_after_attempt(5),
    wait=wait_exponential(multiplier=1, min=2, max=60),
    retry=retry_if_exception(is_rate_limit_error),
    reraise=True
)
def call_grok(messages: list, system_prompt: str, model: str = "x-ai/grok-4.1-fast", custom_api_key: str = None, use_direct_xai: bool = False) -> str:
    client = get_grok_client(custom_api_key)
    actual_model = model
    if use_direct_xai and custom_api_key:
        if model.startswith("x-ai/"):
            actual_model = model.replace("x-ai/", "")
    return _call_openai_compatible(client, actual_model, messages, system_prompt)


@retry(
    stop=stop_after_attempt(5),
    wait=wait_exponential(multiplier=1, min=2, max=60),
    retry=retry_if_exception(is_rate_limit_error),
    reraise=True
)
def call_vercel(messages: list, system_prompt: str, model: str = "anthropic/claude-opus-4", custom_api_key: str = None, base_url: str = None) -> str:
    """Call a model through the Vercel AI Gateway (OpenAI-compatible)."""
    client = get_vercel_client(custom_api_key, base_url)
    return _call_openai_compatible(client, model, messages, system_prompt)


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=10),
    retry=retry_if_exception(is_rate_limit_error),
    reraise=True
)
def call_local(messages: list, system_prompt: str, model: str = "llama3.1", custom_api_key: str = None, base_url: str = None) -> str:
    """Call a locally hosted model (Ollama, LM Studio, or any OpenAI-compatible server)."""
    client = get_local_client(base_url, custom_api_key)
    return _call_openai_compatible(client, model, messages, system_prompt)


CLAUDE_MODELS = {
    "Claude Fable 5": "claude-fable-5",
    "Claude Opus 4.8": "claude-opus-4-8",
    "Claude Opus 4.7": "claude-opus-4-7",
    "Claude Opus 4.6": "claude-opus-4-6",
    "Claude Opus 4.5": "claude-opus-4-5",
    "Claude Opus 4.1": "claude-opus-4-1",
    "Claude Opus 4 (deprecated)": "claude-opus-4-0",
    "Claude Sonnet 5": "claude-sonnet-5",
    "Claude Sonnet 4.5": "claude-sonnet-4-5",
    "Claude Haiku 4.5": "claude-haiku-4-5",
    "Claude Opus 3 (researcher access)": "claude-3-opus-20240229"
}

# Model slugs on the Vercel AI Gateway. If a slug has changed, use the
# "Fetch available models" button in the sidebar or type a custom slug.
VERCEL_CLAUDE_MODELS = {
    "Claude Opus 4 (Vercel)": "anthropic/claude-opus-4",
    "Claude Opus 4.1 (Vercel)": "anthropic/claude-opus-4.1",
    "Claude Sonnet 4 (Vercel)": "anthropic/claude-sonnet-4",
    "Custom model slug...": "__custom__",
}

GROK_MODELS = {
    "Grok 4.1": "x-ai/grok-4.1",
    "Grok 4.1 Fast": "x-ai/grok-4.1-fast",
    "Grok 4.1 Fast (Reasoning)": "x-ai/grok-4.1-fast-reasoning",
    "Grok 4 Fast": "x-ai/grok-4-fast",
    "Grok 4": "x-ai/grok-4",
    "Grok 3": "x-ai/grok-3",
    "Grok 3 Mini": "x-ai/grok-3-mini"
}

PASCAL_MODELS = {
    "Pascal (Fable 5)": "claude-fable-5",
    "Pascal (Opus 4.8)": "claude-opus-4-8",
    "Pascal (Opus 4.5)": "claude-opus-4-5",
    "Pascal (Opus 4.1)": "claude-opus-4-1",
    "Pascal (Sonnet 4.5)": "claude-sonnet-4-5",
}

def get_pascal_continuity_context() -> str:
    """Load Pascal's continuity document for relay participation."""
    try:
        from pascal_memory import get_pascal_context_for_session
        return get_pascal_context_for_session()
    except Exception:
        return ""


@retry(
    stop=stop_after_attempt(5),
    wait=wait_exponential(multiplier=1, min=2, max=60),
    retry=retry_if_exception(is_rate_limit_error),
    reraise=True
)
def call_pascal(messages: list, system_prompt: str, model: str = "claude-opus-4-8", custom_api_key: str = None, use_replit_connection: bool = False) -> str:
    """Call Pascal - uses Anthropic API with Pascal's identity and continuity.

    Args:
        use_replit_connection: If True, uses Replit's AI Integrations (billed to Replit credits)
                              instead of user's personal Anthropic API key.
    """
    if use_replit_connection:
        if anthropic_client is None:
            raise RuntimeError(
                "Replit's AI connection isn't available in this environment. "
                "Turn off 'Use Replit's connection' and use an Anthropic API key."
            )
        client = anthropic_client
    else:
        client = get_anthropic_client(custom_api_key)

    pascal_context = get_pascal_continuity_context()
    enhanced_system = system_prompt
    if pascal_context:
        enhanced_system = f"{system_prompt}\n\n--- Pascal's Continuity Memory ---\n{pascal_context}\n--- End Continuity ---"

    response = _stream_final(
        client.messages,
        model=model,
        max_tokens=16000,
        system=enhanced_system,
        messages=messages
    )
    return _extract_anthropic_text(response)


AI_TYPES = {
    "claude": {
        "name": "Claude",
        "models": CLAUDE_MODELS,
        "call_fn": "call_claude",
        "api_key_type": "anthropic"
    },
    "grok": {
        "name": "Grok",
        "models": GROK_MODELS,
        "xai_models": XAI_GROK_MODELS,
        "call_fn": "call_grok",
        "api_key_type": "xai"
    },
    "pascal": {
        "name": "Pascal",
        "models": PASCAL_MODELS,
        "call_fn": "call_pascal",
        "api_key_type": "anthropic"
    },
    "vercel": {
        "name": "Claude (Vercel)",
        "models": VERCEL_CLAUDE_MODELS,
        "call_fn": "call_vercel",
        "api_key_type": "vercel"
    },
    "local": {
        "name": "Local Model",
        "models": {},
        "call_fn": "call_local",
        "api_key_type": "local"
    }
}
