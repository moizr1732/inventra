import httpx
from sqlalchemy.exc import OperationalError

import app.services.groq_service as groq
from app.core.config import settings
from app.main import app
from tests.helpers import count_rows, make_item


class _FakeHttpClient:
    """Stand-in for httpx.Client used only by the Groq module, so the test
    client's own HTTP calls are unaffected."""

    def __init__(self, error=None, response=None):
        self._error = error
        self._response = response

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def post(self, *args, **kwargs):
        if self._error is not None:
            raise self._error
        return self._response


def _fake_client(error=None, response=None):
    return lambda *args, **kwargs: _FakeHttpClient(error=error, response=response)


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


def test_groq_timeout_falls_back_to_rules_and_never_crashes(client, monkeypatch):
    monkeypatch.setattr(settings, "ASSISTANT_LLM_ENABLED", True)
    monkeypatch.setattr(settings, "GROQ_API_KEY", "test-key")

    monkeypatch.setattr(groq.httpx, "Client", _fake_client(httpx.ReadTimeout("timed out")))
    response = client.post("/assistant/chat", json={"message": "Gibberish zzqx unknown words"})
    assert response.status_code == 200
    assert response.json()["intent"] == "clarification"


def test_rules_still_answer_when_groq_is_down(client, monkeypatch):
    item = make_item(client)
    monkeypatch.setattr(settings, "ASSISTANT_LLM_ENABLED", True)
    monkeypatch.setattr(settings, "GROQ_API_KEY", "test-key")

    monkeypatch.setattr(groq.httpx, "Client", _fake_client(httpx.ConnectError("no route")))
    response = client.post("/assistant/chat", json={"message": f"Do we need to buy more {item['item_code']}?"})
    assert response.json()["intent"] == "risk"


def test_only_the_latest_message_is_sent_to_the_language_model(client, monkeypatch):
    sent = {}

    def capture(message):
        sent["message"] = message
        return None

    monkeypatch.setattr("app.assistant.engine.llm_enabled", lambda: True)
    monkeypatch.setattr("app.assistant.engine.classify_with_llm", capture)
    first = client.post("/assistant/chat", json={"message": "Tell me about Confidential Widget"}).json()
    client.post("/assistant/chat", json={"message": "Wibble wobble frabjous", "conversation_id": first["conversation_id"]})
    assert sent["message"] == "Wibble wobble frabjous"


def test_llm_classifier_output_is_restricted_to_known_labels(monkeypatch):
    monkeypatch.setattr(settings, "ASSISTANT_LLM_ENABLED", True)
    monkeypatch.setattr(settings, "GROQ_API_KEY", "test-key")

    class FakeResponse:
        status_code = 200

        def raise_for_status(self):
            return None

        def json(self):
            return {"choices": [{"message": {"content": '{"intents": ["risk", "delete_everything", "forecast"]}'}}]}

    monkeypatch.setattr(groq.httpx, "Client", _fake_client(response=FakeResponse()))
    assert groq.classify_with_llm("anything") == ["risk", "forecast"]


def test_llm_disabled_by_default_makes_no_network_call(client, monkeypatch):
    called = {"n": 0}

    def spy_client(*args, **kwargs):
        called["n"] += 1
        raise AssertionError("network must not be used")

    monkeypatch.setattr(groq.httpx, "Client", spy_client)
    client.post("/assistant/chat", json={"message": "Unrecognised words here"})
    assert called["n"] == 0


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
