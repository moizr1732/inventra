import pytest
from datetime import date

from tests.helpers import count_rows, get_item_row, make_item, seed_continuous


def chat(client, message, conversation_id=None):
    payload = {"message": message}
    if conversation_id is not None:
        payload["conversation_id"] = conversation_id
    response = client.post("/assistant/chat", json=payload)
    assert response.status_code == 200, response.text
    return response.json()


@pytest.fixture()
def cotton(client):
    """FAB-001 Cotton Fabric: 100 on hand, lead time 5, 10 per day consumed."""
    item = make_item(client, on_hand=100, safety_stock=20, lead_time_days=5)
    seed_continuous(item["id"], 10)
    return item


# ---- social ----------------------------------------------------------------

def test_greeting_gets_a_greeting_not_an_item_error(client):
    body = chat(client, "Hi")
    assert body["intent"] == "greeting"
    assert "Hello" in body["answer"]
    assert "couldn't identify" not in body["answer"]


def test_how_are_you_and_thanks_and_goodbye(client):
    assert chat(client, "How are you?")["intent"] == "how_are_you"
    assert chat(client, "Thanks!")["intent"] == "thanks"
    assert chat(client, "Bye")["intent"] == "farewell"


def test_capabilities_explain_read_only_boundary(client):
    body = chat(client, "What can you do?")
    assert body["intent"] == "help"
    assert "read-only" in body["answer"]


def test_small_talk_does_not_touch_business_data(client, cotton):
    chat(client, "Hi there")
    assert count_rows("assistant_messages") == 2


# ---- item questions and risk ------------------------------------------------

def test_risk_question_by_name_returns_live_figures(client, cotton):
    body = chat(client, "Do we need to purchase more cotton fabric?")
    assert body["intent"] == "risk"
    assert "FAB-001" in body["answer"]
    assert "Available stock: 100" in body["answer"]
    assert "Inventory database" in body["sources"]


def test_item_code_question(client, cotton):
    body = chat(client, "What is the forecast for FAB-001?")
    assert body["intent"] == "forecast"
    assert "Demand forecast for FAB-001" in body["answer"]


def test_follow_up_questions_resolve_it_from_conversation(client, cotton):
    first = chat(client, "Tell me about Cotton Fabric.")
    cid = first["conversation_id"]
    risk = chat(client, "Is it at risk?", cid)
    assert "FAB-001" in risk["answer"]
    forecast = chat(client, "What about its forecast?", cid)
    assert forecast["intent"] == "forecast" and "FAB-001" in forecast["answer"]
    why = chat(client, "Why is it risky?", cid)
    assert "How this was calculated" in why["answer"]


def test_pronoun_without_context_asks_which_item(client, cotton):
    body = chat(client, "Is it at risk?")
    assert body["intent"] == "clarification"
    assert "name or code" in body["answer"]


def test_ambiguous_partial_name_asks_instead_of_guessing(client, cotton):
    make_item(client, code="FAB-002", name="Cotton Thread", on_hand=5)
    body = chat(client, "Tell me about cotton")
    assert body["intent"] == "clarification"
    assert "more than one item" in body["answer"]
    assert "FAB-001" in body["answer"] and "FAB-002" in body["answer"]


def test_multiple_requests_in_one_message_are_all_answered(client, cotton):
    body = chat(client, "Show me the stock position for Cotton Fabric, tell me whether it is at risk, and show its demand forecast.")
    assert {"inventory", "risk", "forecast"} <= set(body["intent"].split("+"))
    assert "Available" in body["answer"]
    assert "Stock risk for FAB-001" in body["answer"]
    assert "Demand forecast for FAB-001" in body["answer"]


def test_forecast_without_item_asks_which_one(client, cotton):
    body = chat(client, "Forecast demand")
    assert "Which item" in body["answer"]


def test_risk_question_without_item_ranks_all_items(client, cotton):
    make_item(client, code="LIN-001", name="Linen Fabric", on_hand=500)
    body = chat(client, "Which products are at risk of running out?")
    assert body["intent"] == "risk"
    assert "Stock risk across 2 active items" in body["answer"]


def test_inventory_summary_lists_active_items(client, cotton):
    body = chat(client, "Show me the inventory overview")
    assert "Current inventory position" in body["answer"]
    assert "FAB-001" in body["answer"]


def test_answers_never_reuse_old_numbers_from_memory(client, cotton):
    first = chat(client, "How much stock do we have of FAB-001?")
    assert "100" in first["answer"]
    cid = first["conversation_id"]
    # Stock changes outside the chat; the next answer must reflect the database.
    client.post("/consumption", json={
        "inventory_item_id": cotton["id"],
        "consumption_date": date.today().isoformat(),
        "quantity_consumed": "40",
    })
    second = chat(client, "How much stock do we have of FAB-001?", cid)
    assert "Available: 60 m" in second["answer"]
    assert "100 m" not in second["answer"]


def test_zero_demand_item_is_explained_without_error(client):
    make_item(client, code="NEW-1", name="Rare Thread", on_hand=10)
    body = chat(client, "Do we need to buy more Rare Thread?")
    assert body["intent"] == "risk"
    assert "No demand data" in body["answer"]


def test_new_item_forecast_explains_insufficient_history(client):
    make_item(client, code="NEW-2", name="Fresh Silk", on_hand=10)
    body = chat(client, "What is the forecast for Fresh Silk?")
    assert "not available yet" in body["answer"]


# ---- what-if ----------------------------------------------------------------

def test_what_if_scenario_is_computed_and_never_changes_live_data(client, cotton):
    before = get_item_row(cotton["id"])
    body = chat(client, "What if demand increases by 20% for FAB-001?")
    assert body["intent"] == "scenario"
    assert "no live records were changed" in body["answer"]
    # Average demand 10/day rises to 12/day.
    assert "Average daily demand: 10 m now, 12 m in the scenario" in body["answer"]
    assert "Reorder point: 70 m now, 80 m in the scenario" in body["answer"]
    assert "What-if simulation (not saved)" in body["sources"]
    assert get_item_row(cotton["id"]) == before


def test_what_if_without_percentage_asks_for_one(client, cotton):
    body = chat(client, "What if demand increases for FAB-001?")
    assert "percentage" in body["answer"]


def test_what_if_on_item_without_demand_is_explained(client):
    make_item(client, code="NEW-3", name="Idle Wool", on_hand=10)
    body = chat(client, "What if demand increases by 10% for Idle Wool?")
    assert "no consumption has been recorded" in body["answer"]


# ---- purchase orders ---------------------------------------------------------

def test_outstanding_orders_are_filtered_to_the_named_item(client, cotton):
    other = make_item(client, code="LIN-001", name="Linen Fabric")
    fab = client.post("/purchase-orders", json={
        "po_number": "PO-FAB", "inventory_item_id": cotton["id"], "supplier_name": "Acme",
        "ordered_quantity": "50", "order_date": "2026-01-01",
    }).json()
    client.post("/purchase-orders", json={
        "po_number": "PO-LIN", "inventory_item_id": other["id"], "supplier_name": "Beta",
        "ordered_quantity": "20", "order_date": "2026-01-01",
    })
    body = chat(client, "Show outstanding purchase orders for FAB-001")
    assert body["intent"] == "purchase_orders"
    assert fab["po_number"] in body["answer"]
    assert "PO-LIN" not in body["answer"]


def test_all_purchase_orders_when_no_item_named(client, cotton):
    client.post("/purchase-orders", json={
        "po_number": "PO-ALL", "inventory_item_id": cotton["id"], "supplier_name": "Acme",
        "ordered_quantity": "5", "order_date": "2026-01-01",
    })
    body = chat(client, "Show me all purchase orders")
    assert "PO-ALL" in body["answer"]


# ---- read-only and unsupported -------------------------------------------------

@pytest.mark.parametrize("message", [
    "Create a purchase order for 50 cotton",
    "Approve PO-001",
    "Delete FAB-001",
    "Set the on hand quantity of FAB-001 to 0",
    "Cancel the purchase order for linen",
])
def test_write_requests_are_declined_and_nothing_changes(client, cotton, message):
    before_row = get_item_row(cotton["id"])
    body = chat(client, message)
    assert body["intent"] == "unsupported_action"
    assert "read-only" in body["answer"]
    assert get_item_row(cotton["id"]) == before_row
    assert count_rows("purchase_orders") == 0


def test_forecast_accuracy_is_declined_honestly(client, cotton):
    body = chat(client, "Compare the forecast with actual consumption.")
    assert body["intent"] == "unsupported"
    assert "past forecasts are not stored" in body["answer"]


def test_supplier_performance_is_declined_honestly(client, cotton):
    body = chat(client, "What is our supplier performance?")
    assert body["intent"] == "unsupported"


def test_unrelated_request_gets_guidance_not_a_fabricated_answer(client, cotton):
    body = chat(client, "Tell me a joke about kangaroos")
    assert body["intent"] == "clarification"
    assert "not sure what you're asking" in body["answer"]


def test_sql_injection_text_is_treated_as_plain_text(client, cotton):
    body = chat(client, "'; DROP TABLE inventory_items; --")
    assert body["intent"] == "clarification"
    assert count_rows("inventory_items") == 1


def test_what_if_follow_up_applies_to_the_current_item(client, cotton):
    # The spec example: a scenario question with no item named applies to the item under discussion.
    first = chat(client, "Tell me about Cotton Fabric.")
    body = chat(client, "What if demand increases by 20%?", first["conversation_id"])
    assert body["intent"] == "scenario"
    assert "FAB-001" in body["answer"]


def test_what_if_without_any_context_still_asks_which_item(client, cotton):
    body = chat(client, "What if demand increases by 20%?")
    assert body["intent"] == "clarification"
