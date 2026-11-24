import pytest

from app.assistant.understanding import find_item_tokens, understand


@pytest.mark.parametrize("message,social", [
    ("Hi", "greeting"),
    ("hello there", "greeting"),
    ("Good morning", "greeting"),
    ("How are you?", "how_are_you"),
    ("What can you do?", "capabilities"),
    ("Thanks!", "thanks"),
    ("thank you so much", "thanks"),
    ("Bye", "farewell"),
    ("ok", "acknowledgement"),
])
def test_social_messages_are_recognised(message, social):
    assert understand(message).social == social


def test_greeting_followed_by_question_is_a_question():
    u = understand("Hi, what is the risk on fabric?")
    assert u.social is None
    assert u.greeting_with_request is True
    assert "risk" in u.intents


@pytest.mark.parametrize("message,intent", [
    ("Is it at risk?", "risk"),
    ("What about its forecast?", "forecast"),
    ("Show planning demand for FAB-001", "planning"),
    ("Show outstanding purchase orders", "purchase_orders"),
    ("Which products are at risk of running out?", "risk"),
    ("What is the reorder quantity for it?", "risk"),
    ("Do we need to purchase more cotton fabric?", "risk"),
    ("What is the on hand quantity of FAB-001?", "inventory"),
    ("What is the total inventory value?", "valuation"),
])
def test_intents_are_detected(message, intent):
    assert intent in understand(message).intents


def test_pronoun_references_are_flagged():
    assert understand("Is it at risk?").uses_pronoun
    assert understand("What about its forecast?").uses_pronoun
    assert understand("What is the reorder quantity for it?").uses_pronoun


def test_ambiguous_reference_is_flagged():
    assert understand("What about the other one?").ambiguous_reference


def test_why_is_an_explanation_request():
    assert understand("Why is it risky?").explain


def test_write_requests_are_detected_but_questions_are_not():
    assert understand("Create a purchase order for 50 cotton").write_request
    assert understand("Approve PO-001").write_request
    assert understand("Delete FAB-001").write_request
    assert not understand("Should we order more cotton?").write_request
    assert not understand("What do we need to order?").write_request


def test_percentage_change_is_parsed_with_direction():
    assert understand("What if demand increases by 20%?").percent_change == 20.0
    assert understand("What if demand drops by 15 percent?").percent_change == -15.0


def test_unsupported_topics_are_flagged():
    assert understand("Compare the forecast with actual consumption.").unsupported == "forecast_accuracy"
    assert understand("What is our supplier performance?").unsupported == "supplier_performance"


def test_multiple_requests_produce_multiple_intents():
    u = understand("Show me the stock position for Cotton Fabric, tell me whether it is at risk, and show its demand forecast.")
    assert {"inventory", "risk", "forecast"} <= set(u.intents)


def test_curly_apostrophes_are_normalised():
    assert understand("How\u2019s it going?").social == "how_are_you"


def test_empty_style_input_does_not_crash():
    assert understand("   ").social is None


CANDIDATES = [
    (1, "FAB-001", "Cotton Fabric"),
    (2, "FAB-002", "Cotton Thread"),
    (3, "LIN-001", "Linen Fabric"),
]


def test_exact_item_code_match_is_case_insensitive():
    full, partial = find_item_tokens("need stock of fab-001 please", CANDIDATES)
    assert full == [1] and partial == {}


def test_full_item_name_match():
    full, _ = find_item_tokens("is cotton fabric at risk", CANDIDATES)
    assert full == [1]


def test_partial_word_matches_several_items_and_is_reported_as_partial():
    full, partial = find_item_tokens("tell me about cotton", CANDIDATES)
    assert full == []
    assert partial == {1: 1, 2: 1}


def test_word_boundaries_prevent_false_code_matches():
    # "fab-0010" must not match "FAB-001".
    full, _ = find_item_tokens("fab-0010 is unrelated", CANDIDATES)
    assert full == []


def test_stopwords_do_not_identify_items():
    full, partial = find_item_tokens("what is the stock level", CANDIDATES)
    assert full == [] and partial == {}
