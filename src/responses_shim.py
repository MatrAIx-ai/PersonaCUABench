"""Speak the Responses API while the rest of the pipeline speaks chat completions.

Azure's chat-completions endpoint bills reasoning tokens but never returns the
reasoning, so a Terra or Astra trajectory records how much thinking was paid for
and nothing about what it was. The Responses API on the same deployment returns
a summary of it at no extra charge, and takes the same tools.

Rather than fork the agent loop, this converts in both directions: chat messages
and tool schemas go in, and what comes back quacks like a chat completion --
`resp.choices[0].message.tool_calls`, `resp.usage.prompt_tokens`, and a
`model_dump()` that carries the raw Responses payload, reasoning summary
included, into the stored trajectory.

    python src/responses_shim.py        # offline self-check of both directions
"""
from __future__ import annotations

import json
from typing import Any


def _message(role: str, text: str) -> dict:
    """One typed message item.

    The bare {"role", "content"} shorthand is rejected by this deployment with
    an empty-type error, so every item is spelled out; assistant text is
    output_text, everything else input_text.
    """
    part = "output_text" if role == "assistant" else "input_text"
    return {"type": "message", "role": role,
            "content": [{"type": part, "text": text}]}


def to_input(messages: list[dict]) -> list[dict]:
    """Chat messages -> Responses input items."""
    items: list[dict] = []
    for message in messages:
        role = message.get("role")
        content = message.get("content")
        if role == "tool":
            items.append({"type": "function_call_output",
                          "call_id": message.get("tool_call_id"),
                          "output": str(content or "")})
            continue
        if isinstance(content, list):     # cache_control parts, flattened back
            content = "".join(part.get("text", "") for part in content
                              if isinstance(part, dict))
        if role == "assistant":
            if content:
                items.append(_message("assistant", str(content)))
            for call in message.get("tool_calls") or []:
                function = call.get("function") or {}
                items.append({"type": "function_call",
                              "call_id": call.get("id"),
                              "name": function.get("name"),
                              "arguments": function.get("arguments") or "{}"})
            continue
        items.append(_message(role or "user", str(content or "")))
    return items


def to_tools(tools: list[dict] | None) -> list[dict] | None:
    """Chat tool schemas -> Responses tool schemas (flat, not nested)."""
    if not tools:
        return None
    flat = []
    for tool in tools:
        function = tool.get("function") or {}
        flat.append({"type": "function", "name": function.get("name"),
                     "description": function.get("description"),
                     "parameters": function.get("parameters")})
    return flat


class _Attr:
    """Attribute access over a dict, for code written against the SDK objects."""

    def __init__(self, data: dict):
        self._data = data

    def __getattr__(self, name: str) -> Any:
        value = self._data.get(name)
        if isinstance(value, dict):
            return _Attr(value)
        if isinstance(value, list):
            return [_Attr(v) if isinstance(v, dict) else v for v in value]
        return value

    def model_dump(self, exclude_none: bool = False) -> dict:
        if not exclude_none:
            return self._data
        return {k: v for k, v in self._data.items() if v is not None}


class ChatLike(_Attr):
    """A Responses payload wearing the shape of a chat completion."""

    def __init__(self, raw: dict, message: dict, usage: dict):
        super().__init__({"choices": [{"message": message, "finish_reason": None}],
                          "usage": usage})
        self.raw = raw

    def model_dump(self, exclude_none: bool = False) -> dict:
        # The stored turn keeps the Responses payload itself: the reasoning
        # summary lives there and would be lost by the chat-shaped view.
        return self.raw


def from_response(response) -> ChatLike:
    """A Responses result as a chat completion, keeping the raw payload."""
    raw = (response.model_dump(exclude_none=True)
           if hasattr(response, "model_dump") else dict(response))
    text_parts: list[str] = []
    tool_calls: list[dict] = []
    for item in raw.get("output") or []:
        kind = item.get("type")
        if kind == "message":
            for part in item.get("content") or []:
                if part.get("type") in ("output_text", "text"):
                    text_parts.append(part.get("text") or "")
        elif kind == "function_call":
            tool_calls.append({
                "id": item.get("call_id") or item.get("id"),
                "type": "function",
                "function": {"name": item.get("name"),
                             "arguments": item.get("arguments") or "{}"},
            })
    usage = raw.get("usage") or {}
    message = {"role": "assistant",
               "content": "".join(text_parts) or None,
               "tool_calls": tool_calls or None}
    return ChatLike(raw, message, {
        "prompt_tokens": usage.get("input_tokens") or 0,
        "completion_tokens": usage.get("output_tokens") or 0,
        "prompt_tokens_details": {
            "cached_tokens": (usage.get("input_tokens_details") or {}).get("cached_tokens")},
        "completion_tokens_details": {
            "reasoning_tokens": (usage.get("output_tokens_details") or {}).get("reasoning_tokens")},
    })


def create(client, *, model: str, messages: list[dict], tools=None,
           max_completion_tokens: int | None = None, summary: str = "auto",
           **ignored) -> ChatLike:
    """One Responses call, argued and answered in chat-completions terms.

    temperature is dropped on purpose: the reasoning deployments accept only
    their default, which is what the chat path was already sending.
    """
    kwargs: dict[str, Any] = {"model": model, "input": to_input(messages),
                              "reasoning": {"summary": summary}}
    flat_tools = to_tools(tools)
    if flat_tools:
        kwargs["tools"] = flat_tools
    if max_completion_tokens:
        kwargs["max_output_tokens"] = max_completion_tokens
    return from_response(client.responses.create(**kwargs))


def _self_check() -> None:
    messages = [
        {"role": "system", "content": "rules"},
        {"role": "user", "content": [{"type": "text", "text": "help me",
                                      "cache_control": {"type": "ephemeral"}}]},
        {"role": "assistant", "content": "on it",
         "tool_calls": [{"id": "c1", "type": "function",
                         "function": {"name": "goto", "arguments": '{"tab_id": 1}'}}]},
        {"role": "tool", "tool_call_id": "c1", "content": "PAGE TEXT"},
    ]
    items = to_input(messages)
    assert items[0] == {"type": "message", "role": "system",
                        "content": [{"type": "input_text", "text": "rules"}]}
    assert items[1] == {"type": "message", "role": "user",
                        "content": [{"type": "input_text", "text": "help me"}]}, items[1]
    assert items[2] == {"type": "message", "role": "assistant",
                        "content": [{"type": "output_text", "text": "on it"}]}
    assert items[3] == {"type": "function_call", "call_id": "c1", "name": "goto",
                        "arguments": '{"tab_id": 1}'}
    assert items[4] == {"type": "function_call_output", "call_id": "c1",
                        "output": "PAGE TEXT"}

    tools = [{"type": "function", "function": {"name": "goto", "description": "go",
                                               "parameters": {"type": "object"}}}]
    assert to_tools(tools) == [{"type": "function", "name": "goto",
                                "description": "go", "parameters": {"type": "object"}}]
    assert to_tools(None) is None

    class Raw:
        @staticmethod
        def model_dump(exclude_none=False):
            return {
                "output": [
                    {"type": "reasoning", "summary": [{"type": "summary_text",
                                                       "text": "thinking..."}]},
                    {"type": "function_call", "call_id": "c2", "name": "read_page",
                     "arguments": '{"tab_id": 2}'},
                    {"type": "message", "content": [{"type": "output_text",
                                                     "text": "done"}]},
                ],
                "usage": {"input_tokens": 100, "output_tokens": 40,
                          "input_tokens_details": {"cached_tokens": 64},
                          "output_tokens_details": {"reasoning_tokens": 30}},
            }

    resp = from_response(Raw())
    message = resp.choices[0].message
    assert message.content == "done"
    assert message.tool_calls[0].id == "c2"
    assert message.tool_calls[0].function.name == "read_page"
    assert json.loads(message.tool_calls[0].function.arguments) == {"tab_id": 2}
    assert resp.usage.prompt_tokens == 100 and resp.usage.completion_tokens == 40
    assert resp.usage.prompt_tokens_details.cached_tokens == 64
    assert resp.usage.completion_tokens_details.reasoning_tokens == 30
    # The stored turn keeps the reasoning summary, which the chat view drops.
    assert resp.model_dump()["output"][0]["summary"][0]["text"] == "thinking..."
    # The history entry stays chat-shaped, so the next request converts cleanly.
    history = message.model_dump(exclude_none=True)
    assert history["role"] == "assistant" and history["tool_calls"][0]["id"] == "c2"
    assert to_input([history])[1]["type"] == "function_call"
    print("responses shim self-check OK")


if __name__ == "__main__":
    _self_check()
