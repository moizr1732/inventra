from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.assistant.engine import handle_message
from app.database.session import get_db
from app.models import AssistantConversation, AssistantMessage
from app.services.conversation_memory import (
    create_conversation,
    get_conversation,
    refresh_conversation_summary,
    save_message,
)

router = APIRouter(prefix="/assistant", tags=["AI Assistant"])


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


@router.get("/conversations", response_model=list[ConversationListItem])
def list_conversations(db: Session = Depends(get_db)):
    rows = db.execute(
        select(AssistantConversation, func.count(AssistantMessage.id).label("message_count"))
        .outerjoin(AssistantMessage, AssistantMessage.conversation_id == AssistantConversation.id)
        .group_by(AssistantConversation.id)
        .order_by(AssistantConversation.updated_at.desc())
        .limit(50)
    ).all()
    return [
        ConversationListItem(
            id=c.id, title=c.title, created_at=c.created_at, updated_at=c.updated_at, message_count=n
        )
        for c, n in rows
    ]


@router.get("/conversations/{conversation_id}/messages", response_model=list[ConversationMessageResponse])
def get_conversation_messages(conversation_id: int, db: Session = Depends(get_db)):
    if get_conversation(db, conversation_id) is None:
        raise HTTPException(status_code=404, detail="Conversation not found.")
    messages = db.scalars(
        select(AssistantMessage)
        .where(AssistantMessage.conversation_id == conversation_id)
        .order_by(AssistantMessage.created_at, AssistantMessage.id)
    ).all()
    return [
        ConversationMessageResponse(
            id=m.id, role=m.role, content=m.content, intent=m.intent, created_at=m.created_at
        )
        for m in messages
    ]


@router.delete("/conversations/{conversation_id}")
def delete_conversation(conversation_id: int, db: Session = Depends(get_db)):
    conversation = get_conversation(db, conversation_id)
    if conversation is None:
        raise HTTPException(status_code=404, detail="Conversation not found.")
    db.delete(conversation)
    db.commit()
    return {"message": "Conversation deleted successfully.", "conversation_id": conversation_id}


@router.post("/chat", response_model=AssistantResponse)
def chat_with_assistant(request: AssistantRequest, db: Session = Depends(get_db)):
    """Answer one message. Synchronous on purpose: all work is database reads
    plus an optional, time-limited classifier call, and running it in the
    threadpool avoids blocking the event loop."""
    message = request.message.strip()
    if len(message) < 2:
        raise HTTPException(status_code=422, detail="Please enter a message containing at least two characters.")

    if request.conversation_id is None:
        conversation = create_conversation(db, message)
    else:
        conversation = get_conversation(db, request.conversation_id)
        if conversation is None:
            raise HTTPException(status_code=404, detail="Conversation not found. Start a new conversation.")

    try:
        save_message(db, conversation.id, "user", message)

        result = handle_message(db, conversation, message)

        save_message(db, conversation.id, "assistant", result.answer, intent=result.intent)
        conversation.context_item_id = result.context_item_id
        refresh_conversation_summary(db, conversation)
        conversation.updated_at = datetime.now(timezone.utc)
        db.commit()
    except Exception:
        db.rollback()
        raise

    return AssistantResponse(
        answer=result.answer,
        intent=result.intent,
        sources=result.sources,
        conversation_id=conversation.id,
    )
