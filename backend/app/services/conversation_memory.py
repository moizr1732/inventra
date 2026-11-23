
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import AssistantConversation, AssistantMessage


def get_conversation(
    db: Session,
    conversation_id: int,
) -> AssistantConversation | None:
    return db.scalar(
        select(AssistantConversation).where(
            AssistantConversation.id == conversation_id
        )
    )


def create_conversation(
    db: Session,
    first_message: str,
) -> AssistantConversation:
    title = " ".join(first_message.split())[:200]

    conversation = AssistantConversation(
        title=title or "New conversation",
    )

    db.add(conversation)
    db.flush()

    return conversation


def save_message(
    db: Session,
    conversation_id: int,
    role: str,
    content: str,
    intent: str | None = None,
) -> AssistantMessage:
    message = AssistantMessage(
        conversation_id=conversation_id,
        role=role,
        content=content,
        intent=intent,
    )

    db.add(message)
    db.flush()

    return message


def get_recent_user_messages(
    db: Session,
    conversation_id: int,
    limit: int = 8,
) -> list[AssistantMessage]:
    messages = db.scalars(
        select(AssistantMessage)
        .where(
            AssistantMessage.conversation_id == conversation_id,
            AssistantMessage.role == "user",
        )
        .order_by(
            AssistantMessage.created_at.desc(),
            AssistantMessage.id.desc(),
        )
        .limit(limit)
    ).all()

    return list(reversed(messages))


def build_conversation_context(
    db: Session,
    conversation: AssistantConversation,
) -> str:
    """
    Build language-understanding context from previous user messages.

    Assistant responses and business database results are deliberately
    excluded so current business figures are always retrieved from
    PostgreSQL rather than conversational memory.
    """

    recent_messages = get_recent_user_messages(
        db,
        conversation.id,
        limit=8,
    )

    context_parts = []

    if conversation.summary:
        context_parts.append(
            "Earlier conversation summary:\n"
            + conversation.summary
        )

    if recent_messages:
        previous_questions = "\n".join(
            f"- {message.content}"
            for message in recent_messages
        )

        context_parts.append(
            "Recent previous user messages:\n"
            + previous_questions
        )

    return "\n\n".join(context_parts)


def refresh_conversation_summary(
    db: Session,
    conversation: AssistantConversation,
) -> None:
    """
    Maintain a compact rolling summary using older user messages only.

    This summary preserves conversational topics and references.
    It is not a source of truth for inventory or business figures.
    """

    messages = db.scalars(
        select(AssistantMessage)
        .where(
            AssistantMessage.conversation_id == conversation.id,
            AssistantMessage.role == "user",
        )
        .order_by(
            AssistantMessage.created_at.desc(),
            AssistantMessage.id.desc(),
        )
        .limit(30)
    ).all()

    older_messages = list(reversed(messages))[0:-8]

    if not older_messages:
        conversation.summary = None
        return

    summary_lines = [
        message.content.strip()
        for message in older_messages
        if message.content.strip()
    ]

    conversation.summary = (
        "Earlier user requests and discussion topics:\n"
        + "\n".join(f"- {line}" for line in summary_lines)
    )[:3000]

