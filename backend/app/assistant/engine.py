"""Conversation engine: turns one user message into one answer.

Pipeline
--------
1. Social acts (greeting, thanks, small talk) are answered without touching
   business data.
2. Write requests and unsupported topics are declined with an explanation.
3. Items are resolved from the message, then from the conversation's current
   item for pronouns such as "it" or "that item". Ambiguity causes a question,
   never a guess.
4. Requested intents are answered, possibly several in one message, with every
   figure read from PostgreSQL.
"""
from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.assistant import answers as A
from app.assistant.understanding import Understanding, find_item_tokens, understand
from app.models import AssistantConversation, InventoryItem
from app.services.groq_service import detect_intent

logger = logging.getLogger("inventra.assistant")

MAX_ITEMS_PER_MESSAGE = 3

SOCIAL_REPLIES = {
    "greeting": "Hello! How can I help you with your inventory today?",
    "how_are_you": "I'm doing well, thanks for asking. I'm ready to help you check stock, risks, forecasts and purchase orders.",
    "thanks": "You're welcome! Let me know if you'd like to look at another item.",
    "farewell": "Goodbye! Your conversation is saved, so you can pick it up any time.",
    "acknowledgement": "Glad that helps. What would you like to look at next?",
    "identity": "I'm the Inventra assistant. I answer questions about your inventory, stock risk, demand forecasts and purchase orders, using live data.",
}

CAPABILITIES_TEXT = (
    "I can help you with:\n"
    "- Stock: \"What is the stock position for Cotton Fabric?\"\n"
    "- Risk and replenishment: \"Do we need to buy more Cotton Fabric?\" or \"Which products are at risk of running out?\"\n"
    "- Demand forecasts: \"What is the forecast for FAB-001?\"\n"
    "- Planning demand: \"Show planning demand for FAB-001.\"\n"
    "- Purchase orders: \"Show outstanding purchase orders.\"\n"
    "- What-if simulations: \"What if demand increases by 20% for Cotton Fabric?\"\n"
    "- Follow-ups: \"Is it at risk?\" or \"Why is it risky?\" after naming an item.\n\n"
    "I am read-only. I cannot create, approve or change purchase orders or inventory records."
)

WRITE_REPLY = (
    "I'm a read-only assistant, so I can't create, approve, change or cancel purchase orders or inventory records. "
    "Those actions need to be done in the system by an authorised person. "
    "I can show you the current stock risk and suggested order quantity so you have the facts to act on."
)

UNSUPPORTED_REPLIES = {
    "forecast_accuracy": (
        "I can't compare forecasts with actual consumption yet, because past forecasts are not stored. "
        "I can show the current forecast and the consumption recorded in the last three complete periods."
    ),
    "supplier_performance": (
        "I can't assess supplier performance yet, because delivery history is not tracked in a way I can analyse. "
        "I can show open purchase orders and their supplier names."
    ),
}

UNKNOWN_REPLY = (
    "I'm not sure what you're asking. I can help with stock levels, stock risk and reorder quantities, "
    "demand forecasts, planning demand and purchase orders. "
    "Try asking: \"Do we need to buy more Cotton Fabric?\" or type \"What can you do?\" for more examples."
)

INTENT_NAMES = {"risk", "forecast", "planning", "purchase_orders", "inventory", "valuation", "scenario"}


@dataclass
class EngineResult:
    answer: str
    intent: str
    sources: list[str] = field(default_factory=list)
    context_item_id: int | None = None


def _clarify_item(db: Session, prefix: str) -> str:
    example = db.scalar(
        select(InventoryItem.item_name)
        .where(InventoryItem.is_active.is_(True))
        .order_by(InventoryItem.id)
        .limit(1)
    )
    hint = f", for example \"{example}\"" if example else ""
    return f"{prefix} Please give me the item's name or code{hint}."


def _resolve_items(db: Session, u: Understanding, conversation: AssistantConversation):
    """Return (items, ambiguous_options, reference_problem)."""
    active = list(
        db.scalars(
            select(InventoryItem)
            .where(InventoryItem.is_active.is_(True))
            .order_by(InventoryItem.id)
        ).all()
    )
    by_id = {i.id: i for i in active}
    candidates = [(i.id, i.item_code, i.item_name) for i in active]

    full_ids, partial = find_item_tokens(u.text, candidates)
    if full_ids:
        return [by_id[i] for i in full_ids[:MAX_ITEMS_PER_MESSAGE]], [], None

    if partial:
        best = max(partial.values())
        top = [i for i, score in partial.items() if score == best]
        if len(top) == 1:
            return [by_id[top[0]]], [], None
        return [], [by_id[i] for i in top], None

    if u.ambiguous_reference:
        return [], [], "ambiguous"

    if u.uses_pronoun:
        current = by_id.get(conversation.context_item_id) if conversation.context_item_id else None
        if current is not None:
            return [current], [], None
        return [], [], "no_context"

    return [], [], None


def db_item_by_id(db: Session, item_id: int | None) -> InventoryItem | None:
    if not item_id:
        return None
    item = db.get(InventoryItem, item_id)
    return item if item is not None and item.is_active else None


GROQ_TO_ENGINE = {"inventory_summary": "inventory"}


def _groq_classification(message: str) -> tuple[list[str], bool, str]:
    """Run the existing Groq intent classifier on the latest message only.

    Returns (intents, is_help, item_query). Any failure yields no intents, so the
    rule-based understanding continues to answer.
    """
    try:
        result = asyncio.run(detect_intent(message, ""))
    except Exception:
        logger.warning("Intent classifier call failed; continuing with rule-based understanding.")
        return [], False, ""

    label = result.get("intent", "clarification")
    item_query = result.get("item_query") or ""
    if label == "help":
        return [], True, item_query
    mapped = GROQ_TO_ENGINE.get(label, label)
    return ([mapped] if mapped in INTENT_NAMES else []), False, item_query


def _merge(rule_intents: list[str], groq_intents: list[str]) -> list[str]:
    merged = list(rule_intents)
    for intent in groq_intents:
        if intent not in merged:
            merged.append(intent)
    return merged


def _resolve_item_query(db: Session, item_query: str) -> list[InventoryItem]:
    """Resolve an item named by the classifier, accepting only unambiguous full matches."""
    active = list(db.scalars(select(InventoryItem).where(InventoryItem.is_active.is_(True)).order_by(InventoryItem.id)).all())
    full_ids, _ = find_item_tokens(item_query, [(i.id, i.item_code, i.item_name) for i in active])
    by_id = {i.id: i for i in active}
    return [by_id[i] for i in full_ids[:1]]


def handle_message(db: Session, conversation: AssistantConversation, message: str) -> EngineResult:
    u = understand(message)

    # 1. Social acts.
    if u.social == "capabilities":
        return EngineResult(CAPABILITIES_TEXT, "help", ["Inventra assistant"], conversation.context_item_id)
    if u.social:
        return EngineResult(SOCIAL_REPLIES.get(u.social, UNKNOWN_REPLY), u.social, ["Inventra assistant"], conversation.context_item_id)

    # 2. Read-only boundary.
    if u.write_request:
        return EngineResult(WRITE_REPLY, "unsupported_action", ["Inventra assistant"], conversation.context_item_id)
    if u.unsupported:
        return EngineResult(UNSUPPORTED_REPLIES[u.unsupported], "unsupported", ["Inventra assistant"], conversation.context_item_id)

    # 3. Item resolution.
    items, ambiguous, reference_problem = _resolve_items(db, u, conversation)

    if ambiguous:
        names = "; ".join(f"{i.item_code} ({i.item_name})" for i in ambiguous)
        return EngineResult(
            f"That matches more than one item: {names}. Which one do you mean?",
            "clarification", ["Inventory database"], conversation.context_item_id,
        )
    if reference_problem == "ambiguous":
        return EngineResult(
            "Which item do you mean? Please name it or give its item code.",
            "clarification", ["Inventra assistant"], conversation.context_item_id,
        )
    if reference_problem == "no_context":
        return EngineResult(
            _clarify_item(db, "I'm not sure which item you mean, because we haven't discussed one yet."),
            "clarification", ["Inventra assistant"], conversation.context_item_id,
        )

    intents = list(u.intents)

    # 3a. Groq classification (existing service, unchanged). It sees only the latest
    # message: no database records and no earlier conversation text are sent.
    groq_intents, groq_help, groq_item_query = _groq_classification(message)
    if groq_help and not intents and not items:
        return EngineResult(CAPABILITIES_TEXT, "help", ["Inventra assistant"], conversation.context_item_id)
    intents = _merge(intents, groq_intents)
    if not items and groq_item_query:
        items = _resolve_item_query(db, groq_item_query)

    # 3b. Follow-ups such as "What if demand increases by 20%?" apply to the current item.
    if not items and not ambiguous and intents and any(i in ("forecast", "planning", "scenario") for i in intents):
        current = db_item_by_id(db, conversation.context_item_id)
        if current is not None:
            items = [current]

    # 4. Infer intent for bare item mentions or "why" follow-ups.
    if not intents and items:
        intents = ["inventory"]
    if u.explain and not intents:
        intents = ["risk"]

    if not intents:
        return EngineResult(UNKNOWN_REPLY, "clarification", ["Inventra assistant"], conversation.context_item_id)

    # 6. Required-detail checks (per-intent item checks happen below).
    if "scenario" in intents and u.percent_change is None:
        return EngineResult(
            "What percentage change should I model? For example, \"What if demand increases by 20%?\"",
            "clarification", ["Inventra assistant"], conversation.context_item_id,
        )

    sections: list[str] = []
    sources: list[str] = []
    used: list[str] = []
    needs_item_notes: list[str] = []

    for intent in ("risk", "forecast", "planning", "inventory", "valuation", "purchase_orders", "scenario"):
        if intent not in intents:
            continue
        try:
            if intent == "risk":
                if items:
                    text, src = A.stock_risk_answer(db, items, explain=u.explain)
                else:
                    text, src = A.risk_ranking_answer(db)
            elif intent == "forecast":
                if not items:
                    needs_item_notes.append(_clarify_item(db, "Which item would you like a forecast for?"))
                    continue
                parts = [A.forecast_answer(db, i) for i in items[:MAX_ITEMS_PER_MESSAGE]]
                text = "\n\n".join(t for t, _ in parts)
                src = ["Consumption database", "Three-period moving-average forecast"]
            elif intent == "planning":
                if not items:
                    needs_item_notes.append(_clarify_item(db, "Which item would you like planning demand for?"))
                    continue
                parts = [A.planning_answer(db, i) for i in items[:MAX_ITEMS_PER_MESSAGE]]
                text = "\n\n".join(t for t, _ in parts)
                src = ["Forecasting engine", "Forecast override database"]
            elif intent == "inventory":
                if items:
                    text = "\n\n".join(A.inventory_detail_answer(i)[0] for i in items[:MAX_ITEMS_PER_MESSAGE])
                    src = ["Inventory database"]
                else:
                    text, src = A.inventory_summary_answer(db)
            elif intent == "valuation":
                text, src = A.valuation_answer(db, items[0] if len(items) == 1 else None)
            elif intent == "purchase_orders":
                open_only = any(w in u.text.lower() for w in ("outstanding", "open", "pending", "incoming"))
                text, src = A.purchase_orders_answer(db, items[0] if len(items) == 1 else None, open_only)
            elif intent == "scenario":
                if not items:
                    needs_item_notes.append(_clarify_item(db, "Which item should I model the demand change for?"))
                    continue
                text, src = A.scenario_answer(db, items[0], u.percent_change)
            else:
                continue
        except SQLAlchemyError:
            raise
        except Exception:
            logger.exception("Answer generation failed for intent %s", intent)
            text, src = ("I ran into a problem retrieving the information for this request. Please try again.", ["Inventra assistant"])

        sections.append(text)
        sources.extend(s for s in src if s not in sources)
        used.append(intent)

    sections.extend(needs_item_notes)
    if not sections:
        return EngineResult(UNKNOWN_REPLY, "clarification", ["Inventra assistant"], conversation.context_item_id)

    new_context = items[0].id if items else conversation.context_item_id
    return EngineResult(
        answer="\n\n".join(sections),
        intent="+".join(used) if used else "clarification",
        sources=sources or ["Inventra assistant"],
        context_item_id=new_context,
    )
