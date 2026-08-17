"""Tests document_metadata against a fake httpx client — no real backend
service needs to be running for these to pass.
"""

import httpx

from tools.document_metadata import document_metadata


class _FakeResponse:
    def __init__(self, status_code: int, json_body: dict) -> None:
        self.status_code = status_code
        self._json_body = json_body

    def json(self) -> dict:
        return self._json_body

    def raise_for_status(self) -> None:
        pass  # not exercised by these tests -- see module docstring on error scope


class _FakeAsyncClient:
    def __init__(self, response: _FakeResponse | None, *, connect_error: bool = False) -> None:
        self._response = response
        self._connect_error = connect_error

    async def __aenter__(self) -> "_FakeAsyncClient":
        return self

    async def __aexit__(self, *exc_info: object) -> None:
        return None

    async def get(self, url: str, headers: dict | None = None) -> _FakeResponse:
        if self._connect_error:
            raise httpx.ConnectError("connection refused")
        assert self._response is not None
        return self._response


async def test_document_metadata_returns_backend_response(monkeypatch):
    fake_response = _FakeResponse(200, {"document_id": "doc-1", "filename": "a.pdf"})
    monkeypatch.setattr(
        "tools.document_metadata.httpx.AsyncClient",
        lambda **kwargs: _FakeAsyncClient(fake_response),
    )

    result = await document_metadata("doc-1")

    assert result == {"document_id": "doc-1", "filename": "a.pdf"}


async def test_document_metadata_returns_error_dict_for_missing_document(monkeypatch):
    fake_response = _FakeResponse(404, {})
    monkeypatch.setattr(
        "tools.document_metadata.httpx.AsyncClient",
        lambda **kwargs: _FakeAsyncClient(fake_response),
    )

    result = await document_metadata("missing-id")

    assert "error" in result


async def test_document_metadata_handles_backend_unreachable(monkeypatch):
    monkeypatch.setattr(
        "tools.document_metadata.httpx.AsyncClient",
        lambda **kwargs: _FakeAsyncClient(None, connect_error=True),
    )

    result = await document_metadata("doc-1")

    assert "error" in result
