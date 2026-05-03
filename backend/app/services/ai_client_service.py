"""Unified multi-provider AI client service.

Dispatches to Anthropic, OpenAI, or Google Gemini based on the selected model ID.
Exposes a single `create_message()` entry point that returns a response object
whose `.content` is a list of normalized blocks (with .type, .text, .input, .name, .id),
compatible with the Anthropic SDK response shape so callers can iterate the same way
regardless of provider.

Borrows the dispatch pattern from the Ecran portal.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional, Tuple

from app.config import settings as app_settings

logger = logging.getLogger(__name__)

# ── Public catalogue ─────────────────────────────────────────────────────────

AVAILABLE_MODELS: List[Dict[str, Any]] = [
    # Anthropic
    {
        "id": "claude-sonnet-4-5-20250929",
        "name": "Claude Sonnet 4.5",
        "description": "Best balance of speed and intelligence (recommended)",
        "provider": "anthropic",
    },
    {
        "id": "claude-opus-4-6",
        "name": "Claude Opus 4.6",
        "description": "Most capable; best for complex analysis",
        "provider": "anthropic",
    },
    {
        "id": "claude-haiku-4-5-20251001",
        "name": "Claude Haiku 4.5",
        "description": "Fastest and most cost-effective",
        "provider": "anthropic",
    },
    # OpenAI
    {
        "id": "gpt-4.1",
        "name": "GPT-4.1",
        "description": "1M context, strong reasoning",
        "provider": "openai",
    },
    {
        "id": "gpt-4.1-mini",
        "name": "GPT-4.1 Mini",
        "description": "1M context, fast and affordable",
        "provider": "openai",
    },
    # Gemini
    {
        "id": "gemini-2.5-pro",
        "name": "Gemini 2.5 Pro",
        "description": "1M context, strong analysis",
        "provider": "gemini",
    },
    {
        "id": "gemini-2.5-flash",
        "name": "Gemini 2.5 Flash",
        "description": "1M context, fastest and cheapest",
        "provider": "gemini",
    },
]

DEFAULT_MODEL_ID = "claude-sonnet-4-5-20250929"

_MODEL_IDS = {m["id"] for m in AVAILABLE_MODELS}


def is_valid_model(model_id: str) -> bool:
    return model_id in _MODEL_IDS


def get_provider(model_id: Optional[str]) -> str:
    """Detect provider from model ID prefix. Returns 'anthropic', 'openai', or 'gemini'."""
    if not model_id:
        return "anthropic"
    if model_id.startswith(("gpt-", "o1-", "o3-", "o4-")):
        return "openai"
    if model_id.startswith("gemini-"):
        return "gemini"
    return "anthropic"


# ── Normalized response types (Anthropic-compatible) ────────────────────────

class _NormalizedBlock:
    """Minimal block compatible with Anthropic SDK iteration (.type/.text/.name/.input/.id)."""

    def __init__(
        self,
        block_type: str,
        text: Optional[str] = None,
        name: Optional[str] = None,
        input_data: Optional[Dict[str, Any]] = None,
        block_id: Optional[str] = None,
    ) -> None:
        self.type = block_type
        self.text = text
        self.name = name
        self.input = input_data or {}
        self.id = block_id


class _NormalizedResponse:
    """Minimal response compatible with iterating over `.content`."""

    def __init__(self, blocks: List[_NormalizedBlock], stop_reason: Optional[str] = None) -> None:
        self.content = blocks
        self.stop_reason = stop_reason


# ── Tool schema converters ──────────────────────────────────────────────────

def _convert_tool_to_openai(anthropic_tool: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "type": "function",
        "function": {
            "name": anthropic_tool["name"],
            "description": anthropic_tool.get("description", ""),
            "parameters": anthropic_tool.get("input_schema", {}),
        },
    }


def _convert_tool_to_gemini(anthropic_tool: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "name": anthropic_tool["name"],
        "description": anthropic_tool.get("description", ""),
        "parameters": anthropic_tool.get("input_schema", {}),
    }


# ── Message format translators ──────────────────────────────────────────────

def _extract_text(content: Any) -> str:
    """Pull plain text out of either a string or a list of Anthropic content blocks."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for block in content:
            if isinstance(block, dict):
                if block.get("type") == "text":
                    parts.append(block.get("text", ""))
            else:
                t = getattr(block, "type", None)
                if t == "text":
                    parts.append(getattr(block, "text", "") or "")
        return "\n".join(p for p in parts if p)
    return ""


def _anthropic_messages_to_openai(messages: List[Dict[str, Any]], system: Optional[str]) -> List[Dict[str, Any]]:
    """Translate Anthropic-format messages to OpenAI chat completions format.

    Handles:
    - plain string content → passthrough
    - list of content blocks with text / tool_use / tool_result
    """
    out: List[Dict[str, Any]] = []
    if system:
        out.append({"role": "system", "content": system})

    for msg in messages:
        role = msg.get("role")
        content = msg.get("content")

        if role == "user":
            # Content may be plain string OR a list of tool_result blocks
            if isinstance(content, list):
                # Tool result branch: emit one "tool" message per tool_result block
                emitted_any = False
                for block in content:
                    block_type = block.get("type") if isinstance(block, dict) else getattr(block, "type", None)
                    if block_type == "tool_result":
                        tool_use_id = (
                            block.get("tool_use_id") if isinstance(block, dict)
                            else getattr(block, "tool_use_id", None)
                        )
                        tc = block.get("content") if isinstance(block, dict) else getattr(block, "content", "")
                        out.append({
                            "role": "tool",
                            "tool_call_id": tool_use_id or "",
                            "content": tc if isinstance(tc, str) else json.dumps(tc),
                        })
                        emitted_any = True
                if not emitted_any:
                    # Fallback: treat as text
                    out.append({"role": "user", "content": _extract_text(content)})
            else:
                out.append({"role": "user", "content": content if isinstance(content, str) else str(content)})

        elif role == "assistant":
            text_parts: List[str] = []
            tool_calls: List[Dict[str, Any]] = []
            if isinstance(content, list):
                for block in content:
                    block_type = block.get("type") if isinstance(block, dict) else getattr(block, "type", None)
                    if block_type == "text":
                        t = block.get("text") if isinstance(block, dict) else getattr(block, "text", "")
                        if t:
                            text_parts.append(t)
                    elif block_type == "tool_use":
                        tb_id = block.get("id") if isinstance(block, dict) else getattr(block, "id", "")
                        tb_name = block.get("name") if isinstance(block, dict) else getattr(block, "name", "")
                        tb_input = block.get("input") if isinstance(block, dict) else getattr(block, "input", {})
                        tool_calls.append({
                            "id": tb_id or "",
                            "type": "function",
                            "function": {
                                "name": tb_name or "",
                                "arguments": json.dumps(tb_input or {}),
                            },
                        })
            else:
                if isinstance(content, str):
                    text_parts.append(content)

            msg_out: Dict[str, Any] = {"role": "assistant"}
            msg_out["content"] = "\n".join(text_parts) if text_parts else None
            if tool_calls:
                msg_out["tool_calls"] = tool_calls
            out.append(msg_out)

        else:
            # Unknown role — best-effort passthrough
            out.append({"role": role or "user", "content": _extract_text(content)})

    return out


def _anthropic_messages_to_gemini(messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Translate Anthropic-format messages to Gemini contents list.

    Gemini uses role='user'|'model' and parts=[{text}|{function_call}|{function_response}].
    """
    out: List[Dict[str, Any]] = []
    for msg in messages:
        role = msg.get("role")
        content = msg.get("content")
        gem_role = "model" if role == "assistant" else "user"
        parts: List[Dict[str, Any]] = []

        if isinstance(content, str):
            parts.append({"text": content})
        elif isinstance(content, list):
            for block in content:
                block_type = block.get("type") if isinstance(block, dict) else getattr(block, "type", None)
                if block_type == "text":
                    t = block.get("text") if isinstance(block, dict) else getattr(block, "text", "")
                    if t:
                        parts.append({"text": t})
                elif block_type == "tool_use":
                    tb_name = block.get("name") if isinstance(block, dict) else getattr(block, "name", "")
                    tb_input = block.get("input") if isinstance(block, dict) else getattr(block, "input", {})
                    parts.append({
                        "function_call": {"name": tb_name or "", "args": tb_input or {}}
                    })
                elif block_type == "tool_result":
                    tb_id = (
                        block.get("tool_use_id") if isinstance(block, dict)
                        else getattr(block, "tool_use_id", "")
                    )
                    tc = block.get("content") if isinstance(block, dict) else getattr(block, "content", "")
                    try:
                        payload = json.loads(tc) if isinstance(tc, str) else tc
                    except Exception:
                        payload = {"result": str(tc)}
                    parts.append({
                        "function_response": {
                            "name": tb_id or "tool",
                            "response": payload if isinstance(payload, dict) else {"result": payload},
                        }
                    })
        if parts:
            out.append({"role": gem_role, "parts": parts})
    return out


# ── Response normalizers ────────────────────────────────────────────────────

def _normalize_openai_response(response) -> _NormalizedResponse:
    blocks: List[_NormalizedBlock] = []
    choice = response.choices[0]
    message = choice.message

    if getattr(message, "content", None):
        blocks.append(_NormalizedBlock("text", text=message.content))

    tool_calls = getattr(message, "tool_calls", None) or []
    for tc in tool_calls:
        try:
            args = json.loads(tc.function.arguments) if tc.function.arguments else {}
        except json.JSONDecodeError:
            args = {}
        blocks.append(_NormalizedBlock(
            "tool_use",
            name=tc.function.name,
            input_data=args,
            block_id=tc.id,
        ))

    stop = "tool_use" if tool_calls else (choice.finish_reason or "end_turn")
    return _NormalizedResponse(blocks, stop_reason=stop)


def _proto_to_dict(proto_val: Any) -> Any:
    """Recursively convert protobuf Map/Repeated composites to Python dict/list."""
    if hasattr(proto_val, "items"):
        return {k: _proto_to_dict(v) for k, v in proto_val.items()}
    if hasattr(proto_val, "__iter__") and not isinstance(proto_val, (str, bytes)):
        return [_proto_to_dict(item) for item in proto_val]
    return proto_val


def _normalize_gemini_response(response) -> _NormalizedResponse:
    blocks: List[_NormalizedBlock] = []
    candidates = getattr(response, "candidates", None) or []
    for candidate in candidates:
        parts = getattr(getattr(candidate, "content", None), "parts", None) or []
        for part in parts:
            fc = getattr(part, "function_call", None)
            text = getattr(part, "text", None)
            if fc and getattr(fc, "name", None):
                args = _proto_to_dict(fc.args) if getattr(fc, "args", None) else {}
                # Gemini doesn't return a tool_use_id; synthesize one.
                blocks.append(_NormalizedBlock(
                    "tool_use",
                    name=fc.name,
                    input_data=args if isinstance(args, dict) else {},
                    block_id=f"gemini_tu_{fc.name}_{len(blocks)}",
                ))
            elif text:
                blocks.append(_NormalizedBlock("text", text=text))

    has_tool = any(b.type == "tool_use" for b in blocks)
    return _NormalizedResponse(blocks, stop_reason="tool_use" if has_tool else "end_turn")


# ── Key resolution ──────────────────────────────────────────────────────────

def _resolve_key(
    provider: str,
    tenant_service=None,
    tenant_id: Optional[str] = None,
    explicit_key: Optional[str] = None,
) -> Optional[str]:
    """Pick the API key to use for a given provider.

    Priority: explicit argument > tenant DB > environment/settings.
    """
    if explicit_key:
        return explicit_key

    if tenant_service and tenant_id:
        try:
            if provider == "anthropic":
                k = tenant_service.get_anthropic_api_key(tenant_id)
            elif provider == "openai":
                k = tenant_service.get_openai_api_key(tenant_id)
            elif provider == "gemini":
                k = tenant_service.get_gemini_api_key(tenant_id)
            else:
                k = None
            if k:
                return k
        except Exception:
            pass

    # Fall back to server-level settings (currently Anthropic only)
    if provider == "anthropic":
        return app_settings.anthropic_api_key

    return None


# ── Public entry points ──────────────────────────────────────────────────────

class NoApiKeyError(RuntimeError):
    """Raised when no API key is configured for the selected provider."""


def get_selected_model(tenant_service=None, tenant_id: Optional[str] = None) -> str:
    """Return the tenant's selected model id, or the default."""
    if tenant_service and tenant_id:
        try:
            model = tenant_service.get_selected_model(tenant_id)
            if model and is_valid_model(model):
                return model
        except Exception:
            pass
    return DEFAULT_MODEL_ID


def create_message(
    system: str,
    messages: List[Dict[str, Any]],
    max_tokens: int,
    model: Optional[str] = None,
    tools: Optional[List[Dict[str, Any]]] = None,
    tool_choice: Optional[Dict[str, Any]] = None,
    temperature: Optional[float] = None,
    tenant_service=None,
    tenant_id: Optional[str] = None,
    api_key: Optional[str] = None,
) -> _NormalizedResponse:
    """Unified create-message call that dispatches to the correct provider.

    The returned object's `.content` is a list of normalized blocks matching
    the Anthropic SDK response shape (each has `.type`, `.text`, `.name`, `.input`, `.id`).
    """
    model = model or get_selected_model(tenant_service, tenant_id)
    provider = get_provider(model)
    key = _resolve_key(provider, tenant_service, tenant_id, api_key)
    if not key:
        raise NoApiKeyError(
            f"No API key configured for provider '{provider}'. "
            "Add one in Settings or choose a different model."
        )

    if provider == "anthropic":
        import anthropic
        client = anthropic.Anthropic(api_key=key)
        kwargs: Dict[str, Any] = {
            "model": model,
            "max_tokens": max_tokens,
            "system": system,
            "messages": messages,
        }
        if tools:
            kwargs["tools"] = tools
        if tool_choice:
            kwargs["tool_choice"] = tool_choice
        if temperature is not None:
            kwargs["temperature"] = temperature
        return client.messages.create(**kwargs)

    if provider == "openai":
        import openai
        client = openai.OpenAI(api_key=key)
        oai_messages = _anthropic_messages_to_openai(messages, system)
        kwargs = {
            "model": model,
            "max_tokens": max_tokens,
            "messages": oai_messages,
        }
        if tools:
            kwargs["tools"] = [_convert_tool_to_openai(t) for t in tools]
            if tool_choice and tool_choice.get("type") == "tool":
                kwargs["tool_choice"] = {
                    "type": "function",
                    "function": {"name": tool_choice["name"]},
                }
            else:
                kwargs["tool_choice"] = "auto"
        if temperature is not None:
            kwargs["temperature"] = temperature
        response = client.chat.completions.create(**kwargs)
        return _normalize_openai_response(response)

    if provider == "gemini":
        from google import genai
        from google.genai import types as genai_types
        client = genai.Client(api_key=key)
        contents = _anthropic_messages_to_gemini(messages)
        config_kwargs: Dict[str, Any] = {
            "system_instruction": system,
            "max_output_tokens": max_tokens,
        }
        if temperature is not None:
            config_kwargs["temperature"] = temperature
        if tools:
            fn_decls = [_convert_tool_to_gemini(t) for t in tools]
            config_kwargs["tools"] = [genai_types.Tool(function_declarations=fn_decls)]
            if tool_choice and tool_choice.get("type") == "tool":
                config_kwargs["tool_config"] = genai_types.ToolConfig(
                    function_calling_config=genai_types.FunctionCallingConfig(
                        mode="ANY",
                        allowed_function_names=[tool_choice["name"]],
                    )
                )
        config = genai_types.GenerateContentConfig(**config_kwargs)
        response = client.models.generate_content(
            model=model, contents=contents, config=config,
        )
        return _normalize_gemini_response(response)

    raise NoApiKeyError(f"Unknown provider: {provider}")


def stream_text(
    prompt: str,
    max_tokens: int,
    system: Optional[str] = None,
    model: Optional[str] = None,
    temperature: Optional[float] = None,
    tenant_service=None,
    tenant_id: Optional[str] = None,
    api_key: Optional[str] = None,
):
    """Generator yielding plain text chunks for SSE/streaming use cases.

    Works for Anthropic directly (client.messages.stream), and falls back to
    a single-shot call + emit-at-once for OpenAI/Gemini to keep this helper simple.
    """
    model = model or get_selected_model(tenant_service, tenant_id)
    provider = get_provider(model)
    key = _resolve_key(provider, tenant_service, tenant_id, api_key)
    if not key:
        raise NoApiKeyError(
            f"No API key configured for provider '{provider}'."
        )

    if provider == "anthropic":
        import anthropic
        client = anthropic.Anthropic(api_key=key)
        kwargs: Dict[str, Any] = {
            "model": model,
            "max_tokens": max_tokens,
            "messages": [{"role": "user", "content": prompt}],
        }
        if system:
            kwargs["system"] = system
        if temperature is not None:
            kwargs["temperature"] = temperature
        with client.messages.stream(**kwargs) as stream:
            for text in stream.text_stream:
                yield text
        return

    # For OpenAI/Gemini in this first pass, fall back to non-streaming.
    response = create_message(
        system=system or "",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=max_tokens,
        model=model,
        temperature=temperature,
        tenant_service=tenant_service,
        tenant_id=tenant_id,
        api_key=api_key,
    )
    for block in response.content:
        if block.type == "text" and block.text:
            yield block.text
