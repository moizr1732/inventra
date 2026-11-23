from sqlalchemy import text

from app.database.connection import engine
from app.database.session import SessionLocal
from app.models import AssistantConversation
from tests.helpers import count_rows, make_item, seed_analytics_window


def chat(client, message, conversation_id=None):
    payload = {"message": message}
    if conversation_id is not None:
        payload["conversation_id"] = conversation_id
    response = client.post("/assistant/chat", json=payload)
    assert response.status_code == 200, response.text
    return response.json()


def test_first_message_creates_a_titled_conversation(client):
    body = chat(client, "Show me the inventory overview")
    listing = client.get("/assistant/conversations").json()
    assert listing[0]["id"] == body["conversation_id"]
    assert listing[0]["title"] == "Show me the inventory overview"
    assert listing[0]["message_count"] == 2


def test_both_user_and_assistant_messages_are_persisted(client):
    cid = chat(client, "Hi")["conversation_id"]
    messages = client.get(f"/assistant/conversations/{cid}/messages").json()
    assert [m["role"] for m in messages] == ["user", "assistant"]
    assert messages[1]["intent"] == "greeting"


def test_conversations_are_isolated_from_each_other(client):
    item = make_item(client)
    seed_analytics_window(item["id"], 10)
    a = chat(client, "Tell me about FAB-001")["conversation_id"]
    b = chat(client, "Hi")["conversation_id"]
    # Conversation B has never discussed an item, so "it" must not leak from A.
    body = chat(client, "Is it at risk?", b)
    assert body["intent"] == "clarification"
    # Conversation A still resolves it correctly.
    assert "FAB-001" in chat(client, "Is it at risk?", a)["answer"]


def test_deleting_a_conversation_removes_its_messages(client):
    cid = chat(client, "Hi")["conversation_id"]
    assert client.delete(f"/assistant/conversations/{cid}").status_code == 200
    assert client.get(f"/assistant/conversations/{cid}/messages").status_code == 404
    assert count_rows("assistant_messages") == 0


def test_unknown_conversation_is_not_found(client):
    response = client.post("/assistant/chat", json={"message": "Hi", "conversation_id": 999999})
    assert response.status_code == 404
    assert client.get("/assistant/conversations/999999/messages").status_code == 404
    assert client.delete("/assistant/conversations/999999").status_code == 404


def test_long_conversation_summary_is_incremental_and_bounded(client):
    cid = chat(client, "Opening question about stock")["conversation_id"]
    for i in range(60):
        chat(client, f"Question number {i:02d} " + "x" * 150, cid)

    db = SessionLocal()
    try:
        conversation = db.get(AssistantConversation, cid)
        assert conversation.summary is not None
        assert len(conversation.summary) <= 4000
        # The most recent older question is retained, not dropped by a fixed window.
        assert "Question number 50" in conversation.summary
        assert conversation.summarized_through_id is not None
    finally:
        db.close()


def test_context_item_is_stored_as_id_only(client):
    item = make_item(client)
    seed_analytics_window(item["id"], 1)
    cid = chat(client, "Tell me about FAB-001")["conversation_id"]
    with engine.connect() as conn:
        value = conn.execute(
            text("SELECT context_item_id FROM assistant_conversations WHERE id = :id"), {"id": cid}
        ).scalar()
    assert value == item["id"]


def test_deleting_an_item_clears_conversation_context(client):
    item = make_item(client)
    cid = chat(client, "Tell me about FAB-001")["conversation_id"]
    # Items are soft-deleted in this API, so verify the foreign key directly.
    with engine.begin() as conn:
        conn.execute(text("DELETE FROM inventory_items WHERE id = :id"), {"id": item["id"]})
        value = conn.execute(
            text("SELECT context_item_id FROM assistant_conversations WHERE id = :id"), {"id": cid}
        ).scalar()
    assert value is None
