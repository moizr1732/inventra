"""Persistent conversation memory.

What is stored
--------------
* Every user and assistant message (for display and audit).
* The inventory item the conversation is about (an ID only).
* A rolling summary of older user questions, maintained incrementally.

What is never stored as a fact
------------------------------
Stock quantities, risk levels, forecasts and PO statuses are never taken from
memory. Answers always re-read PostgreSQL, so a stale figure in an old reply
cannot be repeated.
"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import AssistantConversation, AssistantMessage

RECENT_USER_MESSAGES = 8
SUMMARY_MAX_CHARS = 4000


def get_conversation(db: Session, conversation_id: int) -> AssistantConversation | None:
    return db.scalar(select(AssistantConversation).where(AssistantConversation.id == conversation_id))


def create_conversation(db: Session, first_message: str) -> AssistantConversation:
    title = " ".join(first_message.split())[:200] or "New conversation"
    conversation = AssistantConversation(title=title)
    db.add(conversation)
    db.flush()
    return conversation


def save_message(db: Session, conversation_id: int, role: str, content: str, intent: str | None = None) -> AssistantMessage:
    message = AssistantMessage(conversation_id=conversation_id, role=role, content=content, intent=intent)
    db.add(message)
    db.flush()
    return message


def _user_messages(db: Session, conversation_id: int) -> list[AssistantMessage]:
    return list(
        db.scalars(
            select(AssistantMessage)
            .where(AssistantMessage.conversation_id == conversation_id, AssistantMessage.role == "user")
            .order_by(AssistantMessage.id)
        ).all()
    )


def get_recent_user_messages(db: Session, conversation_id: int, limit: int = RECENT_USER_MESSAGES) -> list[AssistantMessage]:
    return _user_messages(db, conversation_id)[-limit:]


def build_conversation_context(db: Session, conversation: AssistantConversation) -> str:
    """Text context for the optional language-model classifier only."""
    parts = []
    if conversation.summary:
        parts.append("Earlier questions:\n" + conversation.summary)
    recent = get_recent_user_messages(db, conversation.id)
    if recent:
        parts.append("Recent questions:\n" + "\n".join(f"- {m.content}" for m in recent))
    return "\n\n".join(parts)


def refresh_conversation_summary(db: Session, conversation: AssistantConversation) -> None:
    """Fold user messages that have left the recent window into the summary.

    Incremental: only messages newer than the watermark are appended, so no
    message is lost or re-summarised. When the summary grows past its limit,
    the oldest text is trimmed.
    """
    messages = _user_messages(db, conversation.id)
    older = messages[:-RECENT_USER_MESSAGES] if len(messages) > RECENT_USER_MESSAGES else []
    watermark = conversation.summarized_through_id or 0
    new_older = [m for m in older if m.id > watermark]
    if not new_older:
        return

    new_lines = [f"- {m.content.strip()}" for m in new_older if m.content.strip()]
    existing = conversation.summary or ""
    combined = (existing + "\n" if existing else "") + "\n".join(new_lines)
    if len(combined) > SUMMARY_MAX_CHARS:
        combined = "...\n" + combined[-(SUMMARY_MAX_CHARS - 4):]

    conversation.summary = combined
    conversation.summarized_through_id = new_older[-1].id
