"""Freeform tool streaming boundaries and ordinary function compatibility."""

import json

import pytest

from omnigent.billing.responses_tools import ResponsesToolBridge


@pytest.mark.asyncio
async def test_custom_input_survives_fragmented_unicode_events_and_closes_source():
    bridge = ResponsesToolBridge({"tools": [{"type": "custom", "name": "apply_patch"}]})
    patch = "*** Begin Patch\n*** Add File: hello.txt\n+世界\n*** End Patch"
    events = [
        {
            "type": "response.output_item.added",
            "item": {
                "type": "function_call",
                "id": "patch",
                "name": "apply_patch",
                "arguments": "",
            },
        },
        {
            "type": "response.function_call_arguments.done",
            "item_id": "patch",
            "arguments": json.dumps({"input": patch}, ensure_ascii=False),
        },
        {
            "type": "response.function_call_arguments.delta",
            "item_id": "shell",
            "delta": "keep function delta",
        },
    ]
    wire = "".join(f"data: {json.dumps(e, ensure_ascii=False)}\r\n\r\n" for e in events).encode()
    closed = []

    async def source():
        try:
            for byte in wire:
                yield bytes([byte])
        finally:
            closed.append(True)

    output = "".join([chunk async for chunk in bridge._stream(source())])
    decoded = [json.loads(line[6:]) for line in output.splitlines() if line.startswith("data: ")]
    assert decoded[0]["item"]["type"] == "custom_tool_call"
    assert decoded[1]["delta"] == patch
    assert decoded[2]["input"] == patch
    assert decoded[3]["type"] == "response.function_call_arguments.delta"
    assert decoded[3]["delta"] == "keep function delta"
    assert closed == [True]


def test_forced_custom_choice_and_normal_function_are_preserved():
    normal = {"type": "function", "name": "exec_command", "parameters": {"type": "object"}}
    body = {
        "tools": [{"type": "custom", "name": "apply_patch"}, normal],
        "tool_choice": {"type": "custom", "name": "apply_patch"},
    }
    bridge = ResponsesToolBridge(body)
    assert bridge.request["tools"][1] == normal
    assert bridge.request["tool_choice"] == {"type": "function", "name": "apply_patch"}
    assert body["tools"][0]["type"] == "custom"
    assert (
        bridge.wrap(
            {"output": [{"type": "function_call", "name": "exec_command", "arguments": "{}"}]}
        )["output"][0]["type"]
        == "function_call"
    )


@pytest.mark.parametrize(
    "raw", ["*** Begin Patch\n*** End Patch", '{"command":["apply_patch","bad"]}']
)
def test_native_tool_receives_unwrapped_syntax_errors_instead_of_transport_failure(raw):
    bridge = ResponsesToolBridge({"tools": [{"type": "custom", "name": "apply_patch"}]})
    result = bridge.wrap(
        {"output": [{"type": "function_call", "name": "apply_patch", "arguments": raw}]}
    )
    assert result["output"][0]["type"] == "custom_tool_call"
    assert result["output"][0]["input"] == raw


def test_models_without_a_registered_patch_tool_receive_correct_capability_instructions():
    body = {
        "instructions": "Keep existing job rules.",
        "tools": [{"type": "function", "name": "exec_command", "parameters": {"type": "object"}}],
    }
    bridge = ResponsesToolBridge(body)
    assert bridge.request["instructions"].startswith(body["instructions"])
    assert "apply_patch is not registered" in bridge.request["instructions"]
    assert "declared JSON argument schema" in bridge.request["instructions"]
    assert body["instructions"] == "Keep existing job rules."


def test_deferred_code_mode_inventory_is_callable_and_namespaced_history_roundtrips():
    js = 'text(await tools.apply_patch("*** Begin Patch\\n*** End Patch"));'
    tool = {"type": "custom", "name": "exec", "description": "Run JavaScript"}
    normal = {"type": "function", "name": "wait", "parameters": {"type": "object"}}
    original = {
        "type": "custom_tool_call",
        "id": "ctc_exec",
        "call_id": "call_exec",
        "namespace": "functions",
        "name": "exec",
        "input": js,
    }
    inventory = {
        "type": "additional_tools",
        "tools": [{"type": "namespace", "name": "functions", "tools": [tool, normal]}],
    }
    body = {
        "tools": [],
        "input": [
            inventory,
            original,
            {"type": "custom_tool_call_output", "call_id": "call_exec", "output": "Success"},
        ],
    }
    bridge = ResponsesToolBridge(body)
    assert [t["name"] for t in bridge.request["tools"]] == ["functions__exec", "functions__wait"]
    assert "await tools.apply_patch(patchText)" in bridge.request["instructions"]
    history = bridge.request["input"]
    assert history[0]["name"] == "functions__exec"
    assert "namespace" not in history[0]
    assert json.loads(history[0]["arguments"]) == {"input": js}
    assert history[1]["type"] == "function_call_output"
    restored = bridge.wrap(
        {
            "output": [
                {
                    "type": "function_call",
                    "id": "ctc_exec",
                    "call_id": "call_exec",
                    "name": "functions__exec",
                    "arguments": json.dumps({"input": js}),
                }
            ]
        }
    )
    assert restored["output"][0] == original
    assert (
        bridge.wrap(
            {"output": [{"type": "function_call", "name": "functions__wait", "arguments": "{}"}]}
        )["output"][0]["namespace"]
        == "functions"
    )
