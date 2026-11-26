"""
API Router for ContextIQ Knowledge-Grounded Conversational Assistant (Phase 8.8).
"""
from __future__ import annotations

import uuid
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.deps import get_current_user_id
from app.db.session import get_db
from app.schemas.assistant import (
    AskAssistantRequest,
    AssistantConversationListResponse,
    AssistantConversationRead,
    StructuredAssistantResponse,
)
from app.services.assistant_service import AssistantService

assistant_router = APIRouter(prefix="/assistant", tags=["assistant"])


class AskResponsePayload(BaseModel):
    conversation_id: uuid.UUID
    message_id: uuid.UUID
    response: StructuredAssistantResponse


@assistant_router.post(
    "/ask",
    response_model=AskResponsePayload,
    summary="Ask the knowledge-grounded assistant a question",
)
def ask_assistant(
    request: AskAssistantRequest,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """
    Submits a query to the ContextIQ assistant.
    The response is grounded strictly in the user's verified tasks, projects,
    goals, behavioral patterns, and historical analytics.
    """
    conv, msg, structured_resp = AssistantService.ask(
        db=db,
        user_id=user_id,
        query=request.query,
        conversation_id=request.conversation_id,
        include_evidence=request.include_evidence,
        include_proposals=request.include_proposals,
    )
    db.commit()
    return AskResponsePayload(
        conversation_id=conv.id,
        message_id=msg.id,
        response=structured_resp,
    )


@assistant_router.get(
    "/conversations",
    response_model=AssistantConversationListResponse,
    summary="List active conversation sessions",
)
def list_conversations(
    include_archived: bool = Query(False, description="Include archived sessions"),
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """
    Lists recent conversation sessions for the authenticated user.
    """
    convs = AssistantService.list_conversations(db=db, user_id=user_id, include_archived=include_archived)
    return AssistantConversationListResponse(conversations=convs, total=len(convs))


@assistant_router.get(
    "/conversations/{conversation_id}",
    response_model=AssistantConversationRead,
    summary="Get conversation history",
)
def get_conversation(
    conversation_id: uuid.UUID,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """
    Retrieves the full message history and structured responses of a conversation.
    """
    conv = AssistantService.get_conversation(db=db, user_id=user_id, conversation_id=conversation_id)
    if not conv:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found or access denied.",
        )
    return conv


@assistant_router.delete(
    "/conversations/{conversation_id}",
    summary="Archive or clear conversation session",
)
def delete_conversation(
    conversation_id: uuid.UUID,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """
    Archives a conversation session so it is no longer shown in active lists.
    """
    success = AssistantService.archive_conversation(db=db, user_id=user_id, conversation_id=conversation_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found or access denied.",
        )
    db.commit()
    return {"status": "archived", "conversation_id": str(conversation_id)}
