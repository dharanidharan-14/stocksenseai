"""
StockSense AI - Voice Assistant API Router
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional

from app.core.database import get_db
from app.schemas.assistant import AssistantCommandRequest, AssistantResponse
from app.services.assistant_service import AssistantService

router = APIRouter(prefix="/api/assistant", tags=["Voice Assistant"])


@router.post("/command", response_model=AssistantResponse)
async def process_assistant_command(
    request: AssistantCommandRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Process natural language voice or typed command.
    Retrieves live information from PostgreSQL or proposes validated stock mutations.
    """
    try:
        response = await AssistantService.process_command(
            db=db,
            command_text=request.text,
            confirmed=request.confirmed,
            action_payload=request.action_payload,
            session_id=request.session_id,
        )
        return response
    except Exception as e:
        return AssistantResponse(
            intent="ERROR",
            speech_text=f"An error occurred while processing your request: {str(e)}",
            display_text=f"Error processing command: {str(e)}",
            error=str(e),
            suggestions=[
                "How much rice stock is left?",
                "Which products expire tomorrow?",
                "What should I reorder today?",
            ],
        )
