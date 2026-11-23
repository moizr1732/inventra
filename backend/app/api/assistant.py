
from datetime import datetime, timezone
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.models import (
    AssistantConversation,
    AssistantMessage,
    InventoryItem,
    PurchaseOrder,
)
from app.services.groq_service import detect_intent
from app.services.conversation_memory import (
    build_conversation_context,
    create_conversation,
    get_conversation,
    get_recent_user_messages,
    refresh_conversation_summary,
    save_message,
)
from app.inventory.stock_risk import get_item_stock_risk
from app.forecasting.demand_forecast import generate_three_month_forecast
from app.forecasting.planning_demand import get_planning_demand


router = APIRouter(prefix="/assistant", tags=["AI Assistant"])


# ---------------------------------------------------------
# API SCHEMAS
# ---------------------------------------------------------

class AssistantRequest(BaseModel):
    message: str = Field(min_length=2, max_length=1000)
    conversation_id: int | None = Field(default=None, ge=1)


class AssistantResponse(BaseModel):
    answer: str
    intent: str
    sources: list[str]
    conversation_id: int


class ConversationListItem(BaseModel):
    id: int
    title: str
    created_at: datetime
    updated_at: datetime
    message_count: int


class ConversationMessageResponse(BaseModel):
    id: int
    role: str
    content: str
    intent: str | None
    created_at: datetime


# ---------------------------------------------------------
# EXISTING BUSINESS HELPERS
# ---------------------------------------------------------

def fmt(value, places=2):
    if value is None:
        return "N/A"

    if isinstance(value, (Decimal, float)):
        return f"{value:,.{places}f}"

    return str(value)


def get_item_by_query(db: Session, message: str):
    items = db.scalars(
        select(InventoryItem)
        .where(InventoryItem.is_active.is_(True))
        .order_by(InventoryItem.id)
    ).all()

    query = message.lower()

    for item in items:
        if item.item_code.lower() in query:
            return item

    for item in items:
        if item.item_name.lower() in query:
            return item

    return None


def get_item_from_previous_messages(
    db: Session,
    conversation_id: int,
    current_message_id: int,
):
    """
    Resolve an item from earlier user messages when the latest
    question uses a contextual reference such as 'it' or 'that item'.

    Only item identity is recovered from conversation history.
    Current business figures are always fetched from the database.
    """
    previous_messages = get_recent_user_messages(
        db,
        conversation_id,
        limit=9,
    )

    for previous in reversed(previous_messages):
        if previous.id == current_message_id:
            continue

        item = get_item_by_query(db, previous.content)

        if item is not None:
            return item

    return None


def inventory_summary(db: Session):
    items = db.scalars(
        select(InventoryItem)
        .where(InventoryItem.is_active.is_(True))
        .order_by(InventoryItem.id)
    ).all()

    if not items:
        return "There are currently no active inventory items.", [
            "Inventory database"
        ]

    lines = []

    for item in items:
        lines.append(
            f"- {item.item_code} ({item.item_name}): "
            f"{fmt(item.available_quantity)} "
            f"{item.unit_of_measure} available."
        )

    return (
        "Here is the current inventory position:\n"
        + "\n".join(lines),
        ["Inventory database"],
    )


def risk_summary(db: Session):
    items = db.scalars(
        select(InventoryItem)
        .where(InventoryItem.is_active.is_(True))
        .order_by(InventoryItem.id)
    ).all()

    if not items:
        return "There are no active inventory items to assess.", [
            "Inventory database"
        ]

    lines = []

    for item in items:
        risk = get_item_stock_risk(db, item.id)

        if risk is None:
            continue

        lines.append(
            f"- {risk['item_code']} ({risk['item_name']}): "
            f"{risk['risk_level'].replace('_', ' ').title()}; "
            f"{fmt(risk['available_quantity'])} available; "
            f"{fmt(risk['days_of_cover'])} days of cover; "
            f"suggested order: "
            f"{fmt(risk['suggested_order_quantity'])}."
        )

    if not lines:
        return "No inventory risk results could be calculated.", [
            "Inventory database",
            "Stock-risk engine",
        ]

    return (
        "Current inventory risk assessment:\n" + "\n".join(lines),
        ["Inventory database", "Consumption analytics", "Stock-risk engine"],
    )


def purchase_order_summary(db: Session):
    orders = db.scalars(
        select(PurchaseOrder).order_by(PurchaseOrder.created_at.desc())
    ).all()

    if not orders:
        return "No purchase orders were found.", [
            "Purchase order database"
        ]

    lines = []

    for order in orders:
        lines.append(
            f"- {order.po_number}: {order.status.replace('_', ' ').title()}; "
            f"supplier: {order.supplier_name}; "
            f"ordered: {fmt(order.ordered_quantity)}; "
            f"received: {fmt(order.received_quantity)}; "
            f"remaining: {fmt(order.remaining_quantity)}."
        )

    return (
        "Purchase order overview:\n" + "\n".join(lines),
        ["Purchase order database"],
    )


def item_answer(db: Session, item: InventoryItem, intent: str):
    if intent == "forecast":
        forecast = generate_three_month_forecast(db, item.id)

        if forecast is None:
            return (
                f"I could not find an active forecast for {item.item_code}.",
                ["Demand forecasting engine"],
            )

        lines = [
            f"- Period {period['forecast_period']} "
            f"({period['start_date']} to {period['end_date']}): "
            f"{fmt(period['predicted_demand'])} "
            f"{item.unit_of_measure}."
            for period in forecast["forecasts"]
        ]

        return (
            f"Demand forecast for {item.item_code} "
            f"({item.item_name}):\n"
            f"Average monthly demand: "
            f"{fmt(forecast['average_monthly_demand'])} "
            f"{item.unit_of_measure}.\n"
            + "\n".join(lines)
            + "\nMethod: three-month moving average.",
            ["Consumption database", "Three-month moving-average forecast"],
        )

    if intent == "planning":
        planning = get_planning_demand(db, item.id)

        if planning is None:
            return (
                "No planning data is available.",
                ["Demand planning engine"],
            )

        lines = []

        for period in planning["planning_periods"]:
            lines.append(
                f"- Period {period['forecast_period']}: "
                f"{fmt(period['final_planning_demand'])} "
                f"{item.unit_of_measure}; "
                f"status: {period['adjustment_status'].replace('_', ' ')}."
            )

        return (
            f"Planning demand for {item.item_code}:\n"
            + "\n".join(lines),
            ["Forecasting engine", "Forecast override database"],
        )

    if intent == "risk":
        risk = get_item_stock_risk(db, item.id)

        if risk is None:
            return (
                "I could not calculate stock risk for this item.",
                ["Stock-risk engine"],
            )

        return (
            f"Stock risk for {item.item_code} ({item.item_name}):\n"
            f"Risk level: {risk['risk_level'].replace('_', ' ').title()}.\n"
            f"Available stock: {fmt(risk['available_quantity'])} "
            f"{item.unit_of_measure}.\n"
            f"Average daily consumption: "
            f"{fmt(risk['average_daily_consumption'], 3)}.\n"
            f"Days of cover: {fmt(risk['days_of_cover'])}.\n"
            f"Reorder point: {fmt(risk['calculated_reorder_point'])}.\n"
            f"Outstanding eligible purchase orders: "
            f"{fmt(risk['outstanding_open_po_quantity'])}.\n"
            f"Suggested order quantity: "
            f"{fmt(risk['suggested_order_quantity'])}.\n"
            f"Replenishment required: "
            f"{'Yes' if risk['requires_replenishment'] else 'No'}.",
            ["Inventory database", "Consumption analytics", "Stock-risk engine"],
        )

    return (
        f"Inventory details for {item.item_code} ({item.item_name}):\n"
        f"Category: {item.category or 'Uncategorized'}.\n"
        f"On-hand quantity: {fmt(item.on_hand_quantity)} "
        f"{item.unit_of_measure}.\n"
        f"Reserved quantity: {fmt(item.reserved_quantity)} "
        f"{item.unit_of_measure}.\n"
        f"Available quantity: {fmt(item.available_quantity)} "
        f"{item.unit_of_measure}.\n"
        f"Reorder level: {fmt(item.reorder_level)} "
        f"{item.unit_of_measure}.\n"
        f"Safety stock: {fmt(item.safety_stock)} "
        f"{item.unit_of_measure}.\n"
        f"Lead time: {item.lead_time_days} days.",
        ["Inventory database"],
    )


# ---------------------------------------------------------
# CONVERSATION HISTORY API
# ---------------------------------------------------------

@router.get("/conversations", response_model=list[ConversationListItem])
def list_conversations(
    db: Session = Depends(get_db),
):
    rows = db.execute(
        select(
            AssistantConversation,
            func.count(AssistantMessage.id).label("message_count"),
        )
        .outerjoin(
            AssistantMessage,
            AssistantMessage.conversation_id == AssistantConversation.id,
        )
        .group_by(AssistantConversation.id)
        .order_by(AssistantConversation.updated_at.desc())
        .limit(50)
    ).all()

    return [
        ConversationListItem(
            id=conversation.id,
            title=conversation.title,
            created_at=conversation.created_at,
            updated_at=conversation.updated_at,
            message_count=message_count,
        )
        for conversation, message_count in rows
    ]


@router.get(
    "/conversations/{conversation_id}/messages",
    response_model=list[ConversationMessageResponse],
)
def get_conversation_messages(
    conversation_id: int,
    db: Session = Depends(get_db),
):
    conversation = get_conversation(db, conversation_id)

    if conversation is None:
        raise HTTPException(
            status_code=404,
            detail="Conversation not found.",
        )

    messages = db.scalars(
        select(AssistantMessage)
        .where(AssistantMessage.conversation_id == conversation_id)
        .order_by(
            AssistantMessage.created_at,
            AssistantMessage.id,
        )
    ).all()

    return [
        ConversationMessageResponse(
            id=message.id,
            role=message.role,
            content=message.content,
            intent=message.intent,
            created_at=message.created_at,
        )
        for message in messages
    ]


@router.delete("/conversations/{conversation_id}")
def delete_conversation(
    conversation_id: int,
    db: Session = Depends(get_db),
):
    conversation = get_conversation(db, conversation_id)

    if conversation is None:
        raise HTTPException(
            status_code=404,
            detail="Conversation not found.",
        )

    try:
        db.delete(conversation)
        db.commit()
    except Exception:
        db.rollback()
        raise

    return {
        "message": "Conversation deleted successfully.",
        "conversation_id": conversation_id,
    }


# ---------------------------------------------------------
# CHAT API WITH PERSISTENT CONVERSATIONS
# ---------------------------------------------------------

@router.post("/chat", response_model=AssistantResponse)
async def chat_with_assistant(
    request: AssistantRequest,
    db: Session = Depends(get_db),
):
    message = request.message.strip()

    if len(message) < 2:
        raise HTTPException(
            status_code=422,
            detail="Please enter a message containing at least two characters.",
        )

    try:
        # Create a new conversation or retrieve the requested one.
        if request.conversation_id is None:
            conversation = create_conversation(db, message)
        else:
            conversation = get_conversation(db, request.conversation_id)

            if conversation is None:
                raise HTTPException(
                    status_code=404,
                    detail="Conversation not found. Start a new conversation.",
                )

        # Build context BEFORE saving the latest message.
        # This prevents the classifier from treating the current question
        # as an earlier conversation turn.
        conversation_context = build_conversation_context(
            db,
            conversation,
        )

        user_message = save_message(
            db,
            conversation.id,
            "user",
            message,
        )

        # Groq interprets language and references only.
        # Business facts continue to come from PostgreSQL.
        classification = await detect_intent(
            message,
            conversation_context=conversation_context,
        )

        intent = classification.get("intent", "clarification")
        item_query = classification.get("item_query", "")

        answer = ""
        sources = []

        if intent == "help":
            answer = (
                "I can answer natural-language questions about Inventra:\n\n"
                "- Show all inventory\n"
                "- Identify inventory risks\n"
                "- Do we need to purchase more cotton fabric?\n"
                "- Show purchase orders\n"
                "- Forecast demand for FAB-001\n"
                "- Show planning demand for FAB-001\n\n"
                "I am read-only. I cannot modify records, approve orders "
                "or place purchase orders."
            )
            sources = ["Inventra assistant"]

        elif intent == "purchase_orders":
            answer, sources = purchase_order_summary(db)

        elif intent == "inventory_summary":
            answer, sources = inventory_summary(db)

        else:
            search_query = f"{message} {item_query}".strip()
            item = get_item_by_query(db, search_query)

            # If the latest message uses a contextual reference and
            # classification did not identify the item, recover the
            # most recently discussed explicit item from this conversation.
            if item is None:
                item = get_item_from_previous_messages(
                    db,
                    conversation.id,
                    user_message.id,
                )

            if item is None:
                if intent == "risk":
                    answer, sources = risk_summary(db)
                    intent = "risk_summary"
                else:
                    answer = (
                        "I couldn't identify a specific inventory item. "
                        "Please mention its product name or item code, "
                        "for example FAB-001 or Cotton Fabric."
                    )
                    intent = "clarification"

            elif intent == "clarification":
                answer = (
                    f"I identified {item.item_code} ({item.item_name}), "
                    "but I'm not sure what you would like to know. "
                    "You can ask about its stock, risk, forecast "
                    "or planning demand."
                )
                sources = ["Inventra assistant"]

            else:
                answer, sources = item_answer(db, item, intent)

        # Persist the assistant reply in the same transaction.
        save_message(
            db,
            conversation.id,
            "assistant",
            answer,
            intent=intent,
        )

        # Keep a rolling summary of older user questions.
        refresh_conversation_summary(db, conversation)

        conversation.updated_at = datetime.now(timezone.utc)

        # Commit the conversation and both messages together.
        db.commit()

        return AssistantResponse(
            answer=answer,
            intent=intent,
            sources=sources,
            conversation_id=conversation.id,
        )

    except Exception:
        db.rollback()
        raise
