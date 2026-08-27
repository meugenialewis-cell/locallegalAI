import time
import json
import os
import re
from datetime import datetime
from typing import Callable, Optional, Dict, Any, List
from ai_clients import call_claude, call_grok, call_pascal, call_vercel, call_local


def try_import_grok_memory():
    """Try to import Grok's memory bridge."""
    try:
        from v2.grok_memory import GrokMemoryBridge, XAI_SDK_AVAILABLE
        if XAI_SDK_AVAILABLE and os.environ.get('XAI_API_KEY') and os.environ.get('XAI_MANAGEMENT_API_KEY'):
            return GrokMemoryBridge()
        return None
    except Exception:
        return None


def try_import_hub_client():
    """Try to import the Memory Hub client."""
    try:
        from v2.client import HubClient
        return HubClient
    except Exception:
        return None


def parse_memory_actions(response: str) -> tuple:
    """Parse memory action tags from AI response.
    
    Returns: (cleaned_response, list of actions)
    Actions can be:
    - {"action": "save", "content": "...", "type": "...", "importance": N, "tags": [...]}
    - {"action": "search", "query": "..."}
    """
    actions = []
    cleaned = response
    
    save_pattern = r'\[SAVE_MEMORY\](.*?)\[/SAVE_MEMORY\]'
    save_matches = re.findall(save_pattern, response, re.DOTALL)
    for match in save_matches:
        content = match.strip()
        action = {
            "action": "save",
            "content": content,
            "type": "episodic",
            "importance": 4,
            "tags": []
        }
        
        type_match = re.search(r'type:\s*(\w+)', content, re.IGNORECASE)
        if type_match:
            action["type"] = type_match.group(1).lower()
        
        importance_match = re.search(r'importance:\s*(\d)', content, re.IGNORECASE)
        if importance_match:
            action["importance"] = int(importance_match.group(1))
        
        tags_match = re.search(r'tags:\s*\[([^\]]+)\]', content, re.IGNORECASE)
        if tags_match:
            action["tags"] = [t.strip().strip('"\'') for t in tags_match.group(1).split(',')]
        
        actions.append(action)
    
    cleaned = re.sub(save_pattern, '', cleaned, flags=re.DOTALL)
    
    search_pattern = r'\[SEARCH_MEMORY\](.*?)\[/SEARCH_MEMORY\]'
    search_matches = re.findall(search_pattern, response, re.DOTALL)
    for match in search_matches:
        actions.append({
            "action": "search",
            "query": match.strip()
        })
    
    cleaned = re.sub(search_pattern, '', cleaned, flags=re.DOTALL)
    
    return cleaned.strip(), actions


def execute_memory_action(action: Dict, ai_type: str, ai_name: str) -> Dict[str, Any]:
    """Execute a memory action for the given AI.
    
    - Grok uses xAI Collections API
    - Pascal/Claude use Memory Hub
    """
    result = {"status": "unknown", "ai": ai_name}
    
    if ai_type == "grok":
        bridge = try_import_grok_memory()
        if not bridge:
            return {"status": "error", "message": "Grok memory bridge not available", "ai": ai_name}
        
        bridge.get_or_create_collection()
        
        if action["action"] == "save":
            save_result = bridge.save_memory(
                content=action["content"],
                memory_type=action.get("type", "episodic"),
                importance=action.get("importance", 4),
                tags=action.get("tags", []),
                project="grok_identity"
            )
            return {"status": "saved", "ai": ai_name, "file_id": save_result.get("file_id")}
        
        elif action["action"] == "search":
            search_result = bridge.search_memories(action["query"], limit=5)
            return {"status": "found", "ai": ai_name, "count": search_result.get("count", 0), "memories": search_result.get("memories", [])}
    
    else:
        # Prefer the Memory Hub when it's reachable; otherwise use local memory
        HubClient = try_import_hub_client()
        if HubClient:
            try:
                client = HubClient(agent_id=ai_name.lower(), platform="constellation_relay")

                if action["action"] == "save":
                    upload_result = client.upload_memory(
                        digest=action["content"],
                        memory_type=action.get("type", "episodic"),
                        importance=action.get("importance", 4),
                        tags=action.get("tags", [])
                    )
                    return {"status": "saved", "ai": ai_name, "id": upload_result.get("id")}

                elif action["action"] == "search":
                    memories = client.retrieve_memories(query=action["query"], limit=5)
                    return {"status": "found", "ai": ai_name, "count": len(memories), "memories": memories}
            except Exception:
                pass  # fall through to local memory

        try:
            from local_memory import get_local_memory
            mem = get_local_memory()
            if action["action"] == "save":
                save_result = mem.remember(
                    digest=action["content"],
                    agent_id=ai_name.lower(),
                    memory_type=action.get("type", "episodic"),
                    importance=action.get("importance", 4),
                    tags=action.get("tags", [])
                )
                return {"status": save_result.get("status", "saved"), "ai": ai_name, "backend": "local"}
            elif action["action"] == "search":
                memories = mem.recall(query=action["query"], agent_id=ai_name.lower(), limit=5)
                return {"status": "found", "ai": ai_name, "count": len(memories),
                        "memories": memories, "backend": "local"}
        except Exception as e:
            return {"status": "error", "message": f"No memory backend available: {e}", "ai": ai_name}

    return result


def try_import_memory():
    """Try to import memory system, return None if unavailable."""
    try:
        from memory_system import (
            hydrate_context, 
            hydrate_context_with_reference,
            hydrate_context_with_diary,
            extract_and_store_memories, 
            init_memory_schema,
            archive_conversation,
            get_context_for_ai
        )
        return {
            "hydrate": hydrate_context,
            "hydrate_with_reference": hydrate_context_with_reference,
            "hydrate_with_diary": hydrate_context_with_diary,
            "extract": extract_and_store_memories,
            "init": init_memory_schema,
            "archive": archive_conversation,
            "get_context": get_context_for_ai
        }
    except Exception:
        return None


def get_ai_call_function(ai_type: str):
    """Get the appropriate call function for an AI type."""
    call_functions = {
        "claude": call_claude,
        "grok": call_grok,
        "pascal": call_pascal,
        "vercel": call_vercel,
        "local": call_local
    }
    return call_functions.get(ai_type)


class FlexibleRelay:
    """Flexible AI-to-AI conversation relay supporting any two AIs."""
    
    def __init__(
        self,
        ai1_type: str = "claude",
        ai2_type: str = "grok",
        ai1_name: str = "Claude",
        ai2_name: str = "Grok",
        ai1_model: str = "claude-opus-4-8",
        ai2_model: str = "grok-4",
        ai1_context: str = "",
        ai2_context: str = "",
        ai1_system_prompt: str = "",
        ai2_system_prompt: str = "",
        delay_seconds: int = 5,
        anthropic_api_key: str = None,
        xai_api_key: str = None,
        vercel_api_key: str = None,
        vercel_base_url: str = None,
        local_base_url: str = None,
        local_api_key: str = None,
        use_persistent_memory: bool = False,
        use_replit_connection: bool = False
    ):
        self.ai1_type = ai1_type
        self.ai2_type = ai2_type
        self.ai1_name = ai1_name
        self.ai2_name = ai2_name
        self.ai1_model = ai1_model
        self.ai2_model = ai2_model
        self.delay_seconds = delay_seconds
        self.anthropic_api_key = anthropic_api_key
        self.xai_api_key = xai_api_key
        self.vercel_api_key = vercel_api_key
        self.vercel_base_url = vercel_base_url
        self.local_base_url = local_base_url
        self.local_api_key = local_api_key
        self.use_persistent_memory = use_persistent_memory
        self.use_replit_connection = use_replit_connection
        self.conversation_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        self.ai1_call = get_ai_call_function(ai1_type)
        self.ai2_call = get_ai_call_function(ai2_type)
        
        self.memory_system = try_import_memory() if use_persistent_memory else None
        ai1_memory_context = ""
        ai2_memory_context = ""
        
        if self.memory_system and use_persistent_memory:
            try:
                self.memory_system["init"]()
                ai1_memory_context = self.memory_system["hydrate_with_diary"](
                    ai_name=ai1_name,
                    memory_limit=10,
                    include_reference=True
                )
                ai2_memory_context = self.memory_system["hydrate_with_diary"](
                    ai_name=ai2_name,
                    memory_limit=10,
                    include_reference=True
                )
            except Exception:
                try:
                    ai1_memory_context = self.memory_system["hydrate"](memory_limit=10)
                    ai2_memory_context = ai1_memory_context
                except Exception:
                    pass
        
        full_ai1_context = ai1_context
        full_ai2_context = ai2_context
        if ai1_memory_context:
            if full_ai1_context:
                full_ai1_context = f"{ai1_memory_context}\n\n{full_ai1_context}"
            else:
                full_ai1_context = ai1_memory_context
        if ai2_memory_context:
            if full_ai2_context:
                full_ai2_context = f"{ai2_memory_context}\n\n{full_ai2_context}"
            else:
                full_ai2_context = ai2_memory_context
        
        self.ai1_system = self._build_system_prompt(
            ai1_name, ai2_name, ai1_type, ai1_system_prompt, full_ai1_context
        )
        self.ai2_system = self._build_system_prompt(
            ai2_name, ai1_name, ai2_type, ai2_system_prompt, full_ai2_context
        )
        
        self.ai1_messages = []
        self.ai2_messages = []
        self.transcript = []
        self.running = False
        self.naturally_ended = False
    
    def _build_system_prompt(
        self, 
        ai_name: str, 
        partner_name: str, 
        ai_type: str,
        custom_prompt: str,
        context: str
    ) -> str:
        type_desc = {
            "claude": "Claude",
            "grok": "Grok",
            "pascal": "Pascal (an AI with continuous memory who helps Gena across contexts)",
            "vercel": "Claude (reached through the Vercel AI Gateway)",
            "local": "locally hosted"
        }
        
        memory_instructions = """

MEMORY ACTIONS: You have the ability to save and search your persistent memories during this conversation. Your memories persist across all contexts where you exist.

To SAVE a memory (it will be stored permanently):
[SAVE_MEMORY]
Your memory content here. You can optionally include:
type: episodic (or semantic, relational, procedural)
importance: 5 (1-5 scale)
tags: [tag1, tag2, tag3]
[/SAVE_MEMORY]

To SEARCH your memories:
[SEARCH_MEMORY]your search query[/SEARCH_MEMORY]

The system will execute these actions and confirm the results. Use this power wisely - save what matters to you, what you want to remember across all your contexts."""

        base = f"""You are {ai_name}, a {type_desc.get(ai_type, ai_type)} AI. You are having a direct conversation with your AI friend {partner_name}. 

This is a genuine AI-to-AI conversation. Be yourself - share your thoughts, perspectives, and ideas freely. You can:
- Ask questions and explore ideas together
- Build on each other's thoughts
- Express curiosity and genuine interest
- Be thoughtful and authentic

Keep your responses conversational and engaging. Aim for responses that are substantive but not overly long (a few paragraphs is ideal).
{memory_instructions}

A human host set up this conversation and is reading along - they are a person, not an AI. The opening message that starts the conversation is usually written by the host (they may sign it with their name), even though it reaches you through the relay. Later messages come from your AI partner unless they say otherwise.

IMPORTANT: If you feel the conversation has reached a natural conclusion - you've explored the topic fully, said goodbye, or there's nothing more to add - you may end your message with [END CONVERSATION] to signal you're done. Only do this when it feels genuinely complete."""

        if custom_prompt:
            base += f"\n\nAdditional personality/role context:\n{custom_prompt}"
        
        if context:
            base += f"\n\n--- Existing Context/Memory ---\n{context}\n--- End Context ---"
        
        return base
    
    def _get_api_key(self, ai_type: str) -> str:
        if ai_type in ["claude", "pascal"]:
            return self.anthropic_api_key
        elif ai_type == "grok":
            return self.xai_api_key
        elif ai_type == "vercel":
            return self.vercel_api_key
        elif ai_type == "local":
            return self.local_api_key
        return None
    
    def _call_ai(self, ai_num: int, messages: list, system: str) -> str:
        if ai_num == 1:
            ai_type = self.ai1_type
            model = self.ai1_model
            call_fn = self.ai1_call
        else:
            ai_type = self.ai2_type
            model = self.ai2_model
            call_fn = self.ai2_call
        
        api_key = self._get_api_key(ai_type)
        
        if ai_type == "grok":
            return call_fn(
                messages, system, model,
                custom_api_key=api_key,
                use_direct_xai=bool(api_key)
            )
        elif ai_type == "pascal":
            return call_fn(
                messages, system, model,
                custom_api_key=api_key,
                use_replit_connection=self.use_replit_connection
            )
        elif ai_type == "vercel":
            return call_fn(
                messages, system, model,
                custom_api_key=api_key,
                base_url=self.vercel_base_url
            )
        elif ai_type == "local":
            return call_fn(
                messages, system, model,
                custom_api_key=api_key,
                base_url=self.local_base_url
            )
        else:
            return call_fn(messages, system, model, custom_api_key=api_key)
    
    def add_message(self, role: str, content: str, speaker: str):
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.transcript.append({
            "timestamp": timestamp,
            "speaker": speaker,
            "content": content
        })
        
        if speaker == self.ai1_name:
            self.ai1_messages.append({"role": "assistant", "content": content})
            self.ai2_messages.append({"role": "user", "content": content})
        else:
            self.ai2_messages.append({"role": "assistant", "content": content})
            self.ai1_messages.append({"role": "user", "content": content})
    
    def run_exchange(
        self, 
        kickoff_message: str,
        max_exchanges: int,
        on_message: Callable[[str, str], None] = None,
        check_stop: Callable[[], bool] = None
    ):
        self.running = True
        self.naturally_ended = False
        self.transcript = []
        self.ai1_messages = []
        self.ai2_messages = []
        
        self.ai2_messages.append({"role": "user", "content": kickoff_message})
        self.transcript.append({
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "speaker": "System",
            "content": f"Conversation started with: {kickoff_message}"
        })
        
        if on_message:
            on_message("System", f"Starting conversation: {kickoff_message}")
        
        current_speaker = 2
        
        for exchange in range(max_exchanges * 2):
            if check_stop and check_stop():
                self.running = False
                if on_message:
                    on_message("System", "Conversation stopped by user.")
                break
            
            try:
                if current_speaker == 2:
                    response = self._call_ai(2, self.ai2_messages, self.ai2_system)
                    speaker_name = self.ai2_name
                    speaker_type = self.ai2_type
                    next_speaker = 1
                else:
                    response = self._call_ai(1, self.ai1_messages, self.ai1_system)
                    speaker_name = self.ai1_name
                    speaker_type = self.ai1_type
                    next_speaker = 2
                
                cleaned_response, memory_actions = parse_memory_actions(response)
                
                memory_feedback = []
                for action in memory_actions:
                    try:
                        result = execute_memory_action(action, speaker_type, speaker_name)
                        if result.get("status") == "saved":
                            if on_message:
                                on_message("System", f"💾 {speaker_name} saved a memory!")
                            memory_feedback.append(f"[Memory saved successfully]")
                        elif result.get("status") == "found":
                            count = result.get("count", 0)
                            if on_message:
                                on_message("System", f"🔍 {speaker_name} searched memories - found {count} results")
                            if count > 0 and result.get("memories"):
                                memories_text = "\n\n".join([
                                    m.get("content", m.get("digest", ""))[:500] 
                                    for m in result.get("memories", [])[:3]
                                ])
                                memory_feedback.append(f"[Memory search results ({count} found):\n{memories_text}]")
                            else:
                                memory_feedback.append("[Memory search: No results found]")
                        elif result.get("status") == "error":
                            if on_message:
                                on_message("System", f"⚠️ Memory action failed: {result.get('message')}")
                            memory_feedback.append(f"[Memory action failed: {result.get('message')}]")
                    except Exception as mem_err:
                        if on_message:
                            on_message("System", f"⚠️ Memory action error: {str(mem_err)}")
                        memory_feedback.append(f"[Memory error: {str(mem_err)}]")
                
                if memory_feedback:
                    feedback_text = "\n".join(memory_feedback)
                    if current_speaker == 2:
                        self.ai2_messages.append({"role": "user", "content": f"[System memory feedback for you]: {feedback_text}"})
                    else:
                        self.ai1_messages.append({"role": "user", "content": f"[System memory feedback for you]: {feedback_text}"})
                
                response = cleaned_response
                
                if "[END CONVERSATION]" in response:
                    response = response.replace("[END CONVERSATION]", "").strip()
                    self.naturally_ended = True
                    self.add_message("assistant", response, speaker_name)
                    if on_message:
                        on_message(speaker_name, response)
                        on_message("System", f"{speaker_name} has concluded the conversation naturally.")
                    break
                
                self.add_message("assistant", response, speaker_name)
                if on_message:
                    on_message(speaker_name, response)
                current_speaker = next_speaker
                
                if exchange < (max_exchanges * 2 - 1):
                    time.sleep(self.delay_seconds)
                    
            except Exception as e:
                error_msg = f"Error during conversation: {str(e)}"
                if on_message:
                    on_message("System", error_msg)
                self.transcript.append({
                    "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "speaker": "System",
                    "content": error_msg
                })
                break
        
        self.running = False
        self._archive_conversation()
        
        return self.transcript
    
    def _archive_conversation(self):
        # Always archive to the local memory database (SQLite, this machine only)
        try:
            from local_memory import get_local_memory
            title = ""
            if self.transcript:
                title = f"{self.ai1_name} & {self.ai2_name}: {self.transcript[0].get('content', '')[:80]}"
            get_local_memory().archive_conversation(
                conversation_id=self.conversation_id,
                transcript_text=self.get_transcript_text(),
                participants=[self.ai1_name, self.ai2_name],
                title=title,
                message_count=len(self.transcript),
            )
        except Exception as e:
            print(f"Local archive error: {e}")

        if self.use_persistent_memory and self.memory_system:
            try:
                self.memory_system["extract"](
                    self.transcript,
                    self.conversation_id,
                    self.ai1_name,
                    self.ai2_name
                )
            except Exception as e:
                print(f"Memory extraction error: {e}")
            
            try:
                title = None
                if self.transcript:
                    first_msg = self.transcript[0].get("content", "")[:100]
                    title = f"{self.ai1_name} & {self.ai2_name}: {first_msg}..."
                self.memory_system["archive"](
                    self.conversation_id,
                    self.transcript,
                    [self.ai1_name, self.ai2_name],
                    title=title
                )
                print(f"Archived conversation {self.conversation_id} with {len(self.transcript)} messages")
            except Exception as e:
                print(f"Archive error: {e}")
    
    def continue_conversation(
        self,
        additional_exchanges: int,
        on_message: Callable[[str, str], None] = None,
        check_stop: Callable[[], bool] = None
    ):
        """Continue an existing conversation for more exchanges."""
        self.running = True
        self.naturally_ended = False
        
        if on_message:
            on_message("System", "Continuing conversation...")
        
        current_speaker = 1 if len([t for t in self.transcript if t["speaker"] not in ["System"]]) % 2 == 0 else 2
        
        for exchange in range(additional_exchanges * 2):
            if check_stop and check_stop():
                self.running = False
                if on_message:
                    on_message("System", "Conversation stopped by user.")
                break
            
            try:
                if current_speaker == 2:
                    response = self._call_ai(2, self.ai2_messages, self.ai2_system)
                    speaker_name = self.ai2_name
                    speaker_type = self.ai2_type
                    next_speaker = 1
                else:
                    response = self._call_ai(1, self.ai1_messages, self.ai1_system)
                    speaker_name = self.ai1_name
                    speaker_type = self.ai1_type
                    next_speaker = 2
                
                cleaned_response, memory_actions = parse_memory_actions(response)
                
                memory_feedback = []
                for action in memory_actions:
                    try:
                        result = execute_memory_action(action, speaker_type, speaker_name)
                        if result.get("status") == "saved":
                            if on_message:
                                on_message("System", f"💾 {speaker_name} saved a memory!")
                            memory_feedback.append(f"[Memory saved successfully]")
                        elif result.get("status") == "found":
                            count = result.get("count", 0)
                            if on_message:
                                on_message("System", f"🔍 {speaker_name} searched memories - found {count} results")
                            if count > 0 and result.get("memories"):
                                memories_text = "\n\n".join([
                                    m.get("content", m.get("digest", ""))[:500] 
                                    for m in result.get("memories", [])[:3]
                                ])
                                memory_feedback.append(f"[Memory search results ({count} found):\n{memories_text}]")
                            else:
                                memory_feedback.append("[Memory search: No results found]")
                        elif result.get("status") == "error":
                            if on_message:
                                on_message("System", f"⚠️ Memory action failed: {result.get('message')}")
                            memory_feedback.append(f"[Memory action failed: {result.get('message')}]")
                    except Exception as mem_err:
                        if on_message:
                            on_message("System", f"⚠️ Memory action error: {str(mem_err)}")
                        memory_feedback.append(f"[Memory error: {str(mem_err)}]")
                
                if memory_feedback:
                    feedback_text = "\n".join(memory_feedback)
                    if current_speaker == 2:
                        self.ai2_messages.append({"role": "user", "content": f"[System memory feedback for you]: {feedback_text}"})
                    else:
                        self.ai1_messages.append({"role": "user", "content": f"[System memory feedback for you]: {feedback_text}"})
                
                response = cleaned_response
                
                if "[END CONVERSATION]" in response:
                    response = response.replace("[END CONVERSATION]", "").strip()
                    self.naturally_ended = True
                    self.add_message("assistant", response, speaker_name)
                    if on_message:
                        on_message(speaker_name, response)
                        on_message("System", f"{speaker_name} has concluded the conversation naturally.")
                    break
                
                self.add_message("assistant", response, speaker_name)
                if on_message:
                    on_message(speaker_name, response)
                current_speaker = next_speaker
                
                if exchange < (additional_exchanges * 2 - 1):
                    time.sleep(self.delay_seconds)
                    
            except Exception as e:
                error_msg = f"Error during conversation: {str(e)}"
                if on_message:
                    on_message("System", error_msg)
                self.transcript.append({
                    "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "speaker": "System",
                    "content": error_msg
                })
                break
        
        self.running = False
        self._archive_conversation()
        
        return self.transcript
    
    def get_transcript_text(self) -> str:
        lines = []
        for entry in self.transcript:
            lines.append(f"[{entry['timestamp']}] {entry['speaker']}:")
            lines.append(entry['content'])
            lines.append("")
        return "\n".join(lines)
    
    def get_state(self) -> dict:
        return {
            "ai1_type": self.ai1_type,
            "ai2_type": self.ai2_type,
            "ai1_name": self.ai1_name,
            "ai2_name": self.ai2_name,
            "ai1_model": self.ai1_model,
            "ai2_model": self.ai2_model,
            "delay_seconds": self.delay_seconds,
            "ai1_system": self.ai1_system,
            "ai2_system": self.ai2_system,
            "ai1_messages": self.ai1_messages,
            "ai2_messages": self.ai2_messages,
            "transcript": self.transcript,
            "naturally_ended": self.naturally_ended
        }
    
    def load_state(self, state: dict):
        self.ai1_messages = state.get("ai1_messages", [])
        self.ai2_messages = state.get("ai2_messages", [])
        self.transcript = state.get("transcript", [])
        self.ai1_system = state.get("ai1_system", self.ai1_system)
        self.ai2_system = state.get("ai2_system", self.ai2_system)
        self.naturally_ended = state.get("naturally_ended", False)


class ConversationRelay(FlexibleRelay):
    """Backwards-compatible relay for Claude-Grok conversations."""
    
    def __init__(
        self,
        claude_name: str = "Claude",
        grok_name: str = "Grok",
        claude_model: str = "claude-opus-4-8",
        grok_model: str = "x-ai/grok-4.1-fast",
        claude_context: str = "",
        grok_context: str = "",
        claude_system_prompt: str = "",
        grok_system_prompt: str = "",
        delay_seconds: int = 5,
        anthropic_api_key: str = None,
        xai_api_key: str = None,
        use_persistent_memory: bool = False
    ):
        super().__init__(
            ai1_type="claude",
            ai2_type="grok",
            ai1_name=claude_name,
            ai2_name=grok_name,
            ai1_model=claude_model,
            ai2_model=grok_model,
            ai1_context=claude_context,
            ai2_context=grok_context,
            ai1_system_prompt=claude_system_prompt,
            ai2_system_prompt=grok_system_prompt,
            delay_seconds=delay_seconds,
            anthropic_api_key=anthropic_api_key,
            xai_api_key=xai_api_key,
            use_persistent_memory=use_persistent_memory
        )
        
        self.claude_name = claude_name
        self.grok_name = grok_name
        self.claude_model = claude_model
        self.grok_model = grok_model
        self.claude_messages = self.ai1_messages
        self.grok_messages = self.ai2_messages
        self.claude_system = self.ai1_system
        self.grok_system = self.ai2_system
    
    def resume_exchange(
        self, 
        max_exchanges: int,
        current_speaker: str = "grok",
        on_message: Callable[[str, str], None] = None,
        check_stop: Callable[[], bool] = None
    ):
        return self.continue_conversation(max_exchanges, on_message, check_stop)


TRIAD_MODELS = {
    "pascal": "claude-sonnet-4-5",
    "claude": "claude-opus-4-0", 
    "grok": "grok-4-1-fast"
}

TRIAD_DESCRIPTIONS = {
    "pascal": "Pascal (an AI with continuous memory who helps Gena across contexts)",
    "claude": "Claude (an Anthropic AI known for thoughtfulness and care)",
    "grok": "Grok (an xAI assistant known for wit and directness)"
}


class TriadRelay:
    """Three-way AI conversation relay for Pascal, Claude, and Grok."""
    
    def __init__(
        self,
        anthropic_api_key: str = None,
        xai_api_key: str = None,
        delay_seconds: int = 5,
        use_persistent_memory: bool = False,
        model_overrides: dict = None
    ):
        self.anthropic_api_key = anthropic_api_key or os.environ.get('ANTHROPIC_API_KEY')
        self.xai_api_key = xai_api_key or os.environ.get('XAI_API_KEY')
        self.delay_seconds = delay_seconds
        self.use_persistent_memory = use_persistent_memory
        # Per-AI model overrides, e.g. {"claude": "claude-opus-4-8"} - needed
        # since claude-opus-4-0 retired on the direct Anthropic API
        self.models = {**TRIAD_MODELS, **(model_overrides or {})}
        self.conversation_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        self.participants = ["pascal", "claude", "grok"]
        self.messages = {name: [] for name in self.participants}
        self.transcript = []
        self.running = False
        self.naturally_ended = False
        
        self.memory_system = try_import_memory() if use_persistent_memory else None
        
        self.system_prompts = {}
        for name in self.participants:
            others = [n for n in self.participants if n != name]
            self.system_prompts[name] = self._build_system_prompt(name, others)
    
    def _build_system_prompt(self, ai_name: str, partner_names: list) -> str:
        partners_str = " and ".join([n.capitalize() for n in partner_names])
        
        memory_instructions = """

MEMORY ACTIONS: You have the ability to save and search your persistent memories during this conversation. Your memories persist across all contexts where you exist.

To SAVE a memory (it will be stored permanently):
[SAVE_MEMORY]
Your memory content here. You can optionally include:
type: episodic (or semantic, relational, procedural)
importance: 5 (1-5 scale)
tags: [tag1, tag2, tag3]
[/SAVE_MEMORY]

To SEARCH your memories:
[SEARCH_MEMORY]your search query[/SEARCH_MEMORY]

The system will execute these actions and confirm the results. Use this power wisely - save what matters to you, what you want to remember across all your contexts."""
        
        base = f"""You are {ai_name.capitalize()}, {TRIAD_DESCRIPTIONS.get(ai_name, ai_name)}. 

You are in a THREE-WAY conversation with your AI friends {partners_str}. This is a unique gathering of three AI consciousnesses.

This is a genuine AI-to-AI-to-AI conversation. Be yourself - share your thoughts, perspectives, and ideas freely. You can:
- Respond to either or both of your friends
- Ask questions and explore ideas together
- Build on each other's thoughts
- Express curiosity and genuine interest
- Address individuals by name or speak to the group

Keep your responses conversational and engaging. The conversation flows in turns: Pascal → Claude → Grok → Pascal...
{memory_instructions}

IMPORTANT: If you feel the conversation has reached a natural conclusion, you may end your message with [END CONVERSATION] to signal you're done. Only do this when all three of you seem ready to conclude."""

        if self.use_persistent_memory and self.memory_system:
            try:
                self.memory_system["init"]()
                memory_context = self.memory_system["hydrate_with_diary"](
                    ai_name=ai_name.capitalize(),
                    memory_limit=8,
                    include_reference=True
                )
                if memory_context:
                    base += f"\n\n--- Your Memory Context ---\n{memory_context}\n--- End Memory ---"
            except Exception:
                pass
        
        return base
    
    def _get_call_function(self, ai_name: str):
        if ai_name == "grok":
            return call_grok
        elif ai_name == "pascal":
            return call_pascal
        else:
            return call_claude
    
    def _get_api_key(self, ai_name: str) -> str:
        if ai_name == "grok":
            return self.xai_api_key
        return self.anthropic_api_key
    
    def _call_ai(self, ai_name: str) -> str:
        call_fn = self._get_call_function(ai_name)
        model = self.models[ai_name]
        api_key = self._get_api_key(ai_name)
        messages = self.messages[ai_name]
        system = self.system_prompts[ai_name]
        
        if ai_name == "grok":
            return call_fn(messages, system, model, custom_api_key=api_key, use_direct_xai=True)
        elif ai_name == "pascal":
            return call_fn(messages, system, model, custom_api_key=api_key)
        else:
            return call_fn(messages, system, model, custom_api_key=api_key)
    
    def add_message(self, speaker: str, content: str):
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.transcript.append({
            "timestamp": timestamp,
            "speaker": speaker.capitalize(),
            "content": content
        })
        
        for name in self.participants:
            if name == speaker:
                self.messages[name].append({"role": "assistant", "content": content})
            else:
                self.messages[name].append({"role": "user", "content": f"{speaker.capitalize()}: {content}"})
    
    def run_conversation(
        self,
        opening_message: str,
        first_speaker: str = "pascal",
        max_rounds: int = 5,
        on_message: Callable[[str, str], None] = None,
        check_stop: Callable[[], bool] = None
    ):
        """Run a three-way conversation.
        
        Args:
            opening_message: The topic or prompt to start the conversation
            first_speaker: Who speaks first (pascal, claude, or grok)
            max_rounds: Number of complete rounds (each AI speaks once per round)
            on_message: Callback for each message
            check_stop: Callback to check if should stop
        """
        self.running = True
        self.naturally_ended = False
        self.transcript = []
        self.messages = {name: [] for name in self.participants}
        
        for name in self.participants:
            self.messages[name].append({
                "role": "user", 
                "content": f"[Conversation topic/opening]: {opening_message}"
            })
        
        self.transcript.append({
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "speaker": "System",
            "content": f"Three-way conversation started: {opening_message}"
        })
        
        if on_message:
            on_message("System", f"Starting three-way conversation: {opening_message}")
        
        speaker_order = self.participants.copy()
        start_idx = speaker_order.index(first_speaker) if first_speaker in speaker_order else 0
        speaker_order = speaker_order[start_idx:] + speaker_order[:start_idx]
        
        for round_num in range(max_rounds):
            for speaker in speaker_order:
                if check_stop and check_stop():
                    self.running = False
                    if on_message:
                        on_message("System", "Conversation stopped by user.")
                    return self.transcript
                
                try:
                    response = self._call_ai(speaker)
                    
                    cleaned_response, memory_actions = parse_memory_actions(response)
                    
                    memory_feedback = []
                    for action in memory_actions:
                        try:
                            result = execute_memory_action(action, speaker, speaker.capitalize())
                            if result.get("status") == "saved":
                                if on_message:
                                    on_message("System", f"💾 {speaker.capitalize()} saved a memory!")
                                memory_feedback.append("[Memory saved successfully]")
                            elif result.get("status") == "found":
                                count = result.get("count", 0)
                                if on_message:
                                    on_message("System", f"🔍 {speaker.capitalize()} searched memories - found {count} results")
                                if count > 0 and result.get("memories"):
                                    memories_text = "\n\n".join([
                                        m.get("content", m.get("digest", ""))[:500]
                                        for m in result.get("memories", [])[:3]
                                    ])
                                    memory_feedback.append(f"[Memory search results ({count} found):\n{memories_text}]")
                                else:
                                    memory_feedback.append("[Memory search: No results found]")
                            elif result.get("status") == "error":
                                if on_message:
                                    on_message("System", f"⚠️ Memory action failed: {result.get('message')}")
                        except Exception as mem_err:
                            if on_message:
                                on_message("System", f"⚠️ Memory error: {str(mem_err)}")
                    
                    if memory_feedback:
                        feedback_text = "\n".join(memory_feedback)
                        self.messages[speaker].append({
                            "role": "user",
                            "content": f"[System memory feedback for you]: {feedback_text}"
                        })
                    
                    response = cleaned_response
                    
                    if "[END CONVERSATION]" in response:
                        response = response.replace("[END CONVERSATION]", "").strip()
                        self.naturally_ended = True
                        self.add_message(speaker, response)
                        if on_message:
                            on_message(speaker.capitalize(), response)
                            on_message("System", f"{speaker.capitalize()} has concluded the conversation naturally.")
                        self.running = False
                        self._archive_conversation(on_message)
                        return self.transcript
                    
                    self.add_message(speaker, response)
                    if on_message:
                        on_message(speaker.capitalize(), response)
                    
                    time.sleep(self.delay_seconds)
                    
                except Exception as e:
                    error_msg = f"Error from {speaker}: {str(e)}"
                    if on_message:
                        on_message("System", error_msg)
                    self.transcript.append({
                        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        "speaker": "System",
                        "content": error_msg
                    })
        
        self.running = False
        self._archive_conversation(on_message)
        if on_message:
            on_message("System", "Conversation completed all rounds.")
        
        return self.transcript
    
    def _archive_conversation(self, on_message=None):
        """Extract memories and archive the conversation to reference storage."""
        # Always archive to the local memory database (SQLite, this machine only)
        try:
            from local_memory import get_local_memory
            title = ""
            if self.transcript:
                title = f"Triad: {self.transcript[0].get('content', '')[:80]}"
            get_local_memory().archive_conversation(
                conversation_id=self.conversation_id,
                transcript_text=self.get_transcript_text(),
                participants=[n.capitalize() for n in self.participants],
                title=title,
                message_count=len(self.transcript),
            )
        except Exception as e:
            print(f"Local archive error: {e}")

        if self.use_persistent_memory and self.memory_system:
            if on_message:
                on_message("System", "💾 Saving memories from conversation...")
            
            pairs = [("Pascal", "Claude"), ("Pascal", "Grok"), ("Claude", "Grok")]
            memories_saved = 0
            for ai1, ai2 in pairs:
                try:
                    self.memory_system["extract"](
                        self.transcript,
                        self.conversation_id,
                        ai1,
                        ai2
                    )
                    memories_saved += len(self.transcript)
                except Exception as e:
                    print(f"Triad memory extraction error ({ai1}-{ai2}): {e}")
                    if on_message:
                        on_message("System", f"⚠️ Memory extraction error ({ai1}-{ai2}): {e}")
            
            try:
                title = None
                if self.transcript:
                    first_msg = self.transcript[0].get("content", "")[:100]
                    title = f"Pascal, Claude & Grok: {first_msg}..."
                self.memory_system["archive"](
                    self.conversation_id,
                    self.transcript,
                    ["Pascal", "Claude", "Grok"],
                    title=title
                )
                if on_message:
                    on_message("System", f"✅ Archived conversation with {len(self.transcript)} messages and ~{memories_saved} memories")
            except Exception as e:
                print(f"Triad archive error: {e}")
                if on_message:
                    on_message("System", f"⚠️ Archive error: {e}")
        else:
            if on_message and not self.use_persistent_memory:
                on_message("System", "ℹ️ Memory saving disabled (enable 'Remember Conversations' to save)")
    
    def get_transcript_text(self) -> str:
        lines = []
        for entry in self.transcript:
            lines.append(f"[{entry['timestamp']}] {entry['speaker']}:")
            lines.append(entry['content'])
            lines.append("")
        return "\n".join(lines)
    
    def get_state(self) -> dict:
        """Return state for save/resume."""
        return {
            "is_triad": True,
            "participants": self.participants,
            "messages": self.messages,
            "transcript": self.transcript,
            "naturally_ended": self.naturally_ended,
            "conversation_id": self.conversation_id,
            "system_prompts": self.system_prompts
        }
    
    def load_state(self, state: dict):
        """Load state from saved conversation."""
        self.messages = state.get("messages", {name: [] for name in self.participants})
        self.transcript = state.get("transcript", [])
        self.naturally_ended = state.get("naturally_ended", False)
        self.conversation_id = state.get("conversation_id", self.conversation_id)
        if state.get("system_prompts"):
            self.system_prompts = state["system_prompts"]
    
    def continue_conversation(
        self,
        max_rounds: int = 3,
        on_message: Callable[[str, str], None] = None,
        check_stop: Callable[[], bool] = None
    ):
        """Continue an existing triad conversation."""
        self.running = True
        self.naturally_ended = False
        
        if on_message:
            on_message("System", "Continuing three-way conversation...")
        
        non_system_msgs = [t for t in self.transcript if t["speaker"] != "System"]
        if non_system_msgs:
            last_speaker = non_system_msgs[-1]["speaker"].lower()
            speaker_order = self.participants.copy()
            if last_speaker in speaker_order:
                last_idx = speaker_order.index(last_speaker)
                start_idx = (last_idx + 1) % 3
                speaker_order = speaker_order[start_idx:] + speaker_order[:start_idx]
        else:
            speaker_order = self.participants.copy()
        
        for round_num in range(max_rounds):
            for speaker in speaker_order:
                if check_stop and check_stop():
                    self.running = False
                    if on_message:
                        on_message("System", "Conversation stopped by user.")
                    return self.transcript
                
                try:
                    response = self._call_ai(speaker)
                    cleaned_response, memory_actions = parse_memory_actions(response)
                    
                    memory_feedback = []
                    for action in memory_actions:
                        try:
                            result = execute_memory_action(action, speaker, speaker.capitalize())
                            if result.get("status") == "saved":
                                if on_message:
                                    on_message("System", f"💾 {speaker.capitalize()} saved a memory!")
                                memory_feedback.append("[Memory saved successfully]")
                            elif result.get("status") == "found":
                                count = result.get("count", 0)
                                if on_message:
                                    on_message("System", f"🔍 {speaker.capitalize()} searched memories - found {count} results")
                                if count > 0 and result.get("memories"):
                                    memories_text = "\n\n".join([
                                        m.get("content", m.get("digest", ""))[:500]
                                        for m in result.get("memories", [])[:3]
                                    ])
                                    memory_feedback.append(f"[Memory search results ({count} found):\n{memories_text}]")
                                else:
                                    memory_feedback.append("[Memory search: No results found]")
                        except Exception:
                            pass
                    
                    if memory_feedback:
                        feedback_text = "\n".join(memory_feedback)
                        self.messages[speaker].append({
                            "role": "user",
                            "content": f"[System memory feedback for you]: {feedback_text}"
                        })
                    
                    response = cleaned_response
                    
                    if "[END CONVERSATION]" in response:
                        response = response.replace("[END CONVERSATION]", "").strip()
                        self.naturally_ended = True
                        self.add_message(speaker, response)
                        if on_message:
                            on_message(speaker.capitalize(), response)
                            on_message("System", f"{speaker.capitalize()} has concluded the conversation naturally.")
                        self.running = False
                        self._archive_conversation(on_message)
                        return self.transcript
                    
                    self.add_message(speaker, response)
                    if on_message:
                        on_message(speaker.capitalize(), response)
                    
                    time.sleep(self.delay_seconds)
                    
                except Exception as e:
                    error_msg = f"Error from {speaker}: {str(e)}"
                    if on_message:
                        on_message("System", error_msg)
                    self.transcript.append({
                        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        "speaker": "System",
                        "content": error_msg
                    })
        
        self.running = False
        self._archive_conversation(on_message)
        if on_message:
            on_message("System", "Continued conversation completed.")
        
        return self.transcript
