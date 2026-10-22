"""Native integration presets use the same contracts as user-supplied MCP specs."""

from pathlib import Path

import pytest

from omnigent.spec.parser import _discover_mcp_servers
from omnigent.tools.mcp import McpServerConnection, clear_discovery_cache
from tests.tools.test_mcp import _make_mcp_tool_def, _mock_mcp_transport

_SKILLS = Path(__file__).resolve().parents[2] / "omnigent/native_skills/skills"


@pytest.mark.parametrize(
    ("skill", "server", "transport"),
    [
        ("context7-mcp", "context7", "stdio"),
        ("21st-ui", "21st", "http"),
        ("reverse-engineer-anything", "rea", "stdio"),
        ("graphify", "graphify", "stdio"),
    ],
)
def test_native_presets_parse_as_real_agent_mcp_configs(skill, server, transport):
    configs = _discover_mcp_servers(_SKILLS / skill, expand_env=False)
    assert len(configs) == 1
    config = configs[0]
    assert (config.name, config.transport) == (server, transport)
    if transport == "stdio":
        assert config.command in {"npx", "uvx"}
        assert any("@" in arg or "==" in arg for arg in config.args)
        assert not any("latest" in arg for arg in config.args)
    else:
        assert config.url == "https://21st.dev/api/mcp"
        assert config.headers == {"x-api-key": "${API_KEY_21ST}"}


@pytest.mark.asyncio
async def test_21st_preset_expands_credentials_and_initializes(monkeypatch):
    monkeypatch.setenv("API_KEY_21ST", "fake-test-key")
    config = _discover_mcp_servers(_SKILLS / "21st-ui")[0]
    assert config.headers == {"x-api-key": "fake-test-key"}
    clear_discovery_cache()
    with _mock_mcp_transport([_make_mcp_tool_def("search")]) as session:
        connection = McpServerConnection(config=config)
        try:
            tools = await connection.connect()
            assert [tool.name for tool in tools] == ["search"]
            session.initialize.assert_awaited_once()
            session.list_tools.assert_awaited_once()
        finally:
            await connection.close()
    clear_discovery_cache()
