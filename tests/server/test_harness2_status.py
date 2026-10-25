"""The benchmark runtime is discoverable without registering a chat executor."""

from unittest.mock import Mock

import httpx
import pytest
from fastapi import FastAPI

from omnigent.errors import ErrorCode, OmnigentError
from omnigent.server.routes import harnesses


@pytest.mark.parametrize("installed,pinned", [(False, False), (True, False), (True, True)])
async def test_benchmark_status_is_read_only(monkeypatch, installed, pinned):
    state = {"installed": installed, "pinned": pinned, "interactive_chat": False}
    inspect = Mock(return_value=state)
    monkeypatch.setattr(harnesses, "installation_status", inspect)
    app = FastAPI()
    app.include_router(harnesses.create_harnesses_router(), prefix="/v1")
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/v1/harnesses/harness2/status")
    assert response.status_code == 200
    assert response.json() == state
    inspect.assert_called_once_with()


async def test_benchmark_status_requires_identity(monkeypatch):
    inspect = Mock()
    monkeypatch.setattr(harnesses, "installation_status", inspect)
    auth = Mock()
    auth.get_user_id.return_value = None
    app = FastAPI()
    app.include_router(harnesses.create_harnesses_router(auth_provider=auth), prefix="/v1")
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        with pytest.raises(OmnigentError) as rejected:
            await client.get("/v1/harnesses/harness2/status")
    assert rejected.value.code == ErrorCode.UNAUTHORIZED
    inspect.assert_not_called()
