"""Bridge client-executed freeform tools through function-only model gateways."""

from __future__ import annotations

import codecs
import hashlib
import json
import re
from collections.abc import AsyncIterable, AsyncIterator
from typing import Any

from starlette.responses import StreamingResponse


class ResponsesToolBridge:
    """Keep Codex's custom-tool wire format while exposing explicit JSON inputs."""

    def __init__(self, body: dict[str, Any]) -> None:
        self.names: set[str] = set()
        self.targets: dict[str, tuple[str | None, str]] = {}
        self.aliases: dict[tuple[str | None, str], str] = {}
        tools: list[dict[str, Any]] = []

        def include(inventory: list[Any], namespace: str | None = None) -> None:
            for tool in inventory:
                if not isinstance(tool, dict) or not isinstance(tool.get("name"), str):
                    continue
                name = tool["name"]
                if tool.get("type") == "namespace":
                    nested = tool.get("tools")
                    if isinstance(nested, list):
                        include(nested, f"{namespace}.{name}" if namespace else name)
                    continue
                if tool.get("type") not in {"custom", "function"}:
                    continue
                key = (namespace, name)
                if key in self.aliases:
                    continue
                alias = f"{namespace}__{name}".replace(".", "__") if namespace else name
                if len(alias) > 64:
                    alias = alias[:50] + "_" + hashlib.sha256(alias.encode()).hexdigest()[:12]
                self.aliases[key] = alias
                self.targets[alias] = key
                description = tool.get("description", "")
                if namespace:
                    description = f"Native tool {namespace}.{name}.\n" + description
                if tool.get("type") == "function":
                    tools.append(
                        {
                            **tool,
                            "name": alias,
                            **({"description": description} if namespace else {}),
                        }
                    )
                    continue
                self.names.add(alias)
                if tool.get("format"):
                    description += "\nRequired input format: " + json.dumps(tool["format"])
                tools.append(
                    {
                        "type": "function",
                        "name": alias,
                        "description": description
                        + '\nCall with {"input": "<exact raw tool input>"}. '
                        "This JSON wrapper is required; input contains the tool's original text.",
                        "parameters": {
                            "type": "object",
                            "properties": {"input": {"type": "string"}},
                            "required": ["input"],
                            "additionalProperties": False,
                        },
                        "strict": True,
                    }
                )

        include(body.get("tools") or [])
        inputs = body.get("input")
        if isinstance(inputs, list):
            for item in inputs:
                if (
                    isinstance(item, dict)
                    and item.get("type") == "additional_tools"
                    and isinstance(item.get("tools"), list)
                ):
                    include(item["tools"])
        self.active = bool(self.names or any(namespace for namespace, _ in self.targets.values()))
        self.request = {**body, "tools": tools}
        if isinstance(inputs, list):
            self.request["input"] = [
                self._history(item)
                for item in inputs
                if not isinstance(item, dict) or item.get("type") != "additional_tools"
            ]
        note = ""
        executor = self.aliases.get(("functions", "exec"))
        if executor in self.names:
            note = (
                f"Runtime tool availability: use {executor} with a JSON object containing "
                "an input "
                "string of JavaScript. Native tools run inside that JavaScript through tools.*. "
                "For patch edits, call await tools.apply_patch(patchText), where patchText is the "
                "raw patch string. Do not invent a standalone apply_patch call or command array."
            )
        elif "exec_command" in self.targets and "apply_patch" not in self.targets:
            note = (
                "Runtime tool availability: apply_patch is not registered in this session. "
                "Do not call it or guess a JSON/command-array wrapper for it. "
                "Edit files using exec_command with its declared JSON argument schema and "
                "ordinary file-editing commands. Use only tools present in the supplied inventory."
            )
        if note:
            self.request["instructions"] = (body.get("instructions") or "") + "\n\n" + note
        choice = body.get("tool_choice")
        if isinstance(choice, dict) and choice.get("type") in {"custom", "function"}:
            alias = self._alias(choice)
            if alias:
                self.request["tool_choice"] = {"type": "function", "name": alias}

    def _alias(self, item: dict[str, Any]) -> str | None:
        name, namespace = item.get("name"), item.get("namespace")
        if not isinstance(name, str) or (namespace is not None and not isinstance(namespace, str)):
            return None
        return self.aliases.get((namespace, name))

    def _history(self, item: Any) -> Any:
        if not isinstance(item, dict):
            return item
        alias = self._alias(item)
        if item.get("type") in {"custom_tool_call", "function_call"} and alias:
            normalized = {**item, "type": "function_call", "name": alias}
            normalized.pop("namespace", None)
            if item["type"] == "custom_tool_call":
                normalized["arguments"] = json.dumps({"input": item.get("input", "")})
                normalized.pop("input", None)
            return normalized
        if item.get("type") == "custom_tool_call_output":
            return {**item, "type": "function_call_output"}
        return item

    @staticmethod
    def _input(arguments: Any) -> str:
        if not isinstance(arguments, str):
            raise ValueError("Custom tool arguments must be JSON text")
        if not arguments:
            return ""
        try:
            value = json.loads(arguments)
        except ValueError:
            return arguments
        raw = value.get("input") if isinstance(value, dict) else value
        if not isinstance(raw, str):
            # Let the native tool return its normal syntax error to the model,
            # rather than breaking transport and replaying the whole request.
            return arguments
        return raw

    def _item(self, item: dict[str, Any]) -> dict[str, Any]:
        name = item.get("name")
        target = self.targets.get(name) if isinstance(name, str) else None
        if item.get("type") != "function_call" or target is None:
            return item
        namespace, name = target
        converted = {**item, "name": name}
        if namespace:
            converted["namespace"] = namespace
        if item["name"] in self.names:
            converted.update(type="custom_tool_call", input=self._input(item.get("arguments", "")))
            converted.pop("arguments", None)
        return converted

    def _response(self, response: dict[str, Any]) -> dict[str, Any]:
        if isinstance(response.get("output"), list):
            return {**response, "output": [self._item(item) for item in response["output"]]}
        return response

    def wrap(self, result: Any) -> Any:
        """Restore custom tool outputs, including complete streamed input events."""
        if not self.active:
            return result
        if not isinstance(result, StreamingResponse):
            return self._response(result)
        return StreamingResponse(
            self._stream(result.body_iterator),
            media_type=result.media_type,
            headers={
                key: value for key, value in result.headers.items() if key != "content-length"
            },
            background=result.background,
        )

    async def _stream(self, source: AsyncIterable[Any]) -> AsyncIterator[str]:
        buffer = ""
        decoder = codecs.getincrementaldecoder("utf-8")()
        custom_ids: set[str] = set()
        sequence = 0

        def translate(frame: str) -> list[str]:
            nonlocal sequence
            data = "\n".join(
                line[5:].lstrip() for line in frame.splitlines() if line.startswith("data:")
            )
            if not data or data == "[DONE]":
                return [frame + "\n\n"]
            try:
                event = json.loads(data)
            except ValueError:
                return [frame + "\n\n"]
            if not isinstance(event, dict):
                return [frame + "\n\n"]
            kind = event.get("type", "")
            item = event.get("item")
            if isinstance(item, dict) and item.get("name") in self.targets:
                if item.get("name") in self.names:
                    custom_ids.add(item.get("id", ""))
                event = {**event, "item": self._item(item)}
            events = [event]
            if event.get("item_id") in custom_ids:
                if kind == "response.function_call_arguments.delta":
                    return []
                if kind == "response.function_call_arguments.done":
                    raw = self._input(event.get("arguments", ""))
                    base = {
                        k: v
                        for k, v in event.items()
                        if k not in {"type", "arguments", "sequence_number"}
                    }
                    events = [
                        {**base, "type": "response.custom_tool_call_input.delta", "delta": raw},
                        {**base, "type": "response.custom_tool_call_input.done", "input": raw},
                    ]
            output = []
            for entry in events:
                if isinstance(entry.get("response"), dict):
                    entry = {**entry, "response": self._response(entry["response"])}
                entry = {**entry, "sequence_number": sequence}
                sequence += 1
                output.append(f"event: {entry['type']}\ndata: {json.dumps(entry)}\n\n")
            return output

        try:
            async for chunk in source:
                buffer += decoder.decode(chunk) if isinstance(chunk, bytes) else chunk
                if len(buffer) > 2_000_000:
                    raise ValueError("Oversized custom-tool stream event")
                while match := re.search(r"\r?\n\r?\n", buffer):
                    frame, buffer = buffer[: match.start()], buffer[match.end() :]
                    for translated in translate(frame):
                        yield translated
            buffer += decoder.decode(b"", final=True)
            if buffer.strip():
                for translated in translate(buffer):
                    yield translated
        finally:
            close = getattr(source, "aclose", None)
            if close is not None:
                await close()
