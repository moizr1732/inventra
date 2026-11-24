import httpx
from sqlalchemy.exc import OperationalError

import app.services.groq_service as groq
from app.core.config import settings
from app.main import app
from tests.helpers import count_rows, make_item


class _FakeAsyncClient:
    """Stand-in for httpx.AsyncClient, used only by these tests. It replaces the
    client reference seen by the Groq module, so the test client is unaffected."""

    def __init__(self, error=None, content=None, status=200):
        self._error = error
        self._content = content
        self._status = status
        self.calls = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    async def post(self, url, headers=None, json=None):
        self.calls.append({"url": url, "json": json})
        if self._error is not None:
            raise self._error
        request = httpx.Request("POST", url)
        return httpx.Response(self._status, request=request, json={
            "choices": [{"message": {"content": self._content}}]
        })


def _patch_async_client(monkeypatch, **kwargs):
    instance = _FakeAsyncClient(**kwargs)
    monkeypatch.setattr(groq.httpx, "AsyncClient", lambda *a, **k: instance)
    return instance


def test_database_outage_returns_clear_503(client, monkeypatch):
    def unavailable(*args, **kwargs):
        raise OperationalError("SELECT 1", {}, Exception("connection refused"))

    monkeypatch.setattr("app.api.assistant.handle_message", unavailable)
    response = client.post("/assistant/chat", json={"message": "Hi"})
    assert response.status_code == 503
    assert "unavailable" in response.json()["detail"]


def test_unexpected_error_returns_generic_500_without_internals(client, monkeypatch):
    def broken(*args, **kwargs):
        raise RuntimeError("secret internal detail: postgres password=hunter2")

    monkeypatch.setattr("app.api.assistant.handle_message", broken)
    response = client.post("/assistant/chat", json={"message": "Hi"})
    assert response.status_code == 500
    body = response.text
    assert "hunter2" not in body
    assert "Traceback" not in body
    assert response.json()["detail"] == "An unexpected error occurred."


def test_a_failed_answer_is_rolled_back_not_half_saved(client, monkeypatch):
    def broken(*args, **kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr("app.api.assistant.handle_message", broken)
    client.post("/assistant/chat", json={"message": "Hi"})
    assert count_rows("assistant_messages") == 0
    assert count_rows("assistant_conversations") == 0


def test_assistant_exposes_no_write_routes_for_inventory():
    # Inspect the public OpenAPI contract: included routers are wrapped by
    # FastAPI, so app.routes alone does not show their paths.
    paths = app.openapi()["paths"]
    assistant = {p: set(ops) for p, ops in paths.items() if p.startswith("/assistant")}
    assert assistant, "assistant routes must be registered"
    assert all(methods <= {"get", "post", "delete"} for methods in assistant.values())
    assert [p for p, m in assistant.items() if "post" in m] == ["/assistant/chat"]
    assert "/inventory" in paths and "post" in paths["/inventory"]


def test_cors_allows_only_configured_origins(client):
    allowed = client.options("/inventory", headers={
        "Origin": "http://localhost:3000",
        "Access-Control-Request-Method": "GET",
    })
    denied = client.options("/inventory", headers={
        "Origin": "https://evil.example.com",
        "Access-Control-Request-Method": "GET",
    })
    assert allowed.headers.get("access-control-allow-origin") == "http://localhost:3000"
    assert "access-control-allow-origin" not in denied.headers


def test_health_reports_database_connected(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["database"] == "connected"


def test_api_key_is_never_echoed_in_responses(client, monkeypatch):
    monkeypatch.setattr(settings, "GROQ_API_KEY", "gsk_super_secret_key_value")
    for path in ("/", "/health", "/assistant/conversations", "/inventory"):
        assert "gsk_super_secret_key_value" not in client.get(path).text


def test_groq_timeout_falls_back_to_rules_and_never_crashes(client, monkeypatch):
    monkeypatch.setattr(settings, "GROQ_API_KEY", "test-key")
    _patch_async_client(monkeypatch, error=httpx.ReadTimeout("timed out"))
    response = client.post("/assistant/chat", json={"message": "Gibberish zzqx unknown words"})
    assert response.status_code == 200
    assert response.json()["intent"] == "clarification"


def test_rules_still_answer_when_groq_is_down(client, monkeypatch):
    item = make_item(client)
    monkeypatch.setattr(settings, "GROQ_API_KEY", "test-key")
    _patch_async_client(monkeypatch, error=httpx.ConnectError("no route"))
    response = client.post("/assistant/chat", json={"message": f"Do we need to buy more {item['item_code']}?"})
    assert response.json()["intent"] == "risk"


def test_groq_classifies_messages_the_rules_do_not_recognise(client, monkeypatch):
    item = make_item(client)
    monkeypatch.setattr(settings, "GROQ_API_KEY", "test-key")
    fake = _patch_async_client(monkeypatch, content='{"intent": "risk", "item_query": "' + item["item_code"] + '"}')
    response = client.post("/assistant/chat", json={"message": "Is our fabric okay for the coming weeks?"})
    body = response.json()
    assert body["intent"] == "risk"
    assert item["item_code"] in body["answer"]
    assert len(fake.calls) == 1


def test_only_the_latest_message_is_sent_to_groq(client, monkeypatch):
    make_item(client)
    monkeypatch.setattr(settings, "GROQ_API_KEY", "test-key")
    fake = _patch_async_client(monkeypatch, content='{"intent": "clarification", "item_query": ""}')
    first = client.post("/assistant/chat", json={"message": "Tell me about FAB-001"}).json()
    client.post("/assistant/chat", json={"message": "Wibble wobble frabjous", "conversation_id": first["conversation_id"]})
    sent_text = fake.calls[-1]["json"]["messages"][1]["content"]
    assert sent_text.endswith("Latest user message:\nWibble wobble frabjous")
    assert "Previous conversation context:\n\n" in sent_text
    assert "Tell me about FAB-001" not in sent_text


def test_groq_unknown_intent_label_is_treated_as_clarification(client, monkeypatch):
    monkeypatch.setattr(settings, "GROQ_API_KEY", "test-key")
    _patch_async_client(monkeypatch, content='{"intent": "delete_everything", "item_query": ""}')
    response = client.post("/assistant/chat", json={"message": "Wipe the warehouse clean"})
    assert response.json()["intent"] == "clarification"


def test_no_key_means_no_network_call(client, monkeypatch):
    monkeypatch.setattr(settings, "GROQ_API_KEY", None)
    def forbidden(*a, **k):
        raise AssertionError("network must not be used without a key")
    monkeypatch.setattr(groq.httpx, "AsyncClient", forbidden)
    response = client.post("/assistant/chat", json={"message": "Unrecognised words here"})
    assert response.status_code == 200


def test_api_key_is_not_leaked_when_groq_fails(client, monkeypatch):
    monkeypatch.setattr(settings, "GROQ_API_KEY", "gsk_leak_check_value")
    _patch_async_client(monkeypatch, error=httpx.ConnectError("boom gsk_leak_check_value"))
    response = client.post("/assistant/chat", json={"message": "Something unclear here"})
    assert "gsk_leak_check_value" not in response.text
