"""
API Router for Natural-Language Productivity Analytics & Decision Intelligence (Phase 8.9).
"""
from __future__ import annotations

import csv
import io
import json
import uuid
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.orm import Session

from app.core.deps import get_current_user_id
from app.db.session import get_db
from app.schemas.analytics_workspace import (
    AnalyticsQueryRequest,
    AnalyticsQueryResponse,
    AnalyticsSuggestionItem,
    SavedAnalyticsQueryCreate,
    SavedAnalyticsQueryListResponse,
    SavedAnalyticsQueryRead,
)
from app.services.natural_language_analytics_service import NaturalLanguageAnalyticsService

nl_analytics_router = APIRouter(prefix="/analytics-workspace", tags=["natural-language-analytics"])


@nl_analytics_router.post(
    "/query",
    response_model=AnalyticsQueryResponse,
    summary="Execute a natural-language productivity analytics query",
)
def execute_natural_language_query(
    request: AnalyticsQueryRequest,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """
    Translates a natural language question into an AST query plan,
    executes it safely via ORM with user data isolation, and returns
    structured calculations, decision recommendations, and visualization specs.
    """
    try:
        return NaturalLanguageAnalyticsService.execute_query(
            db=db,
            user_id=user_id,
            request=request,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@nl_analytics_router.get(
    "/suggestions",
    response_model=List[AnalyticsSuggestionItem],
    summary="List suggested analytical questions",
)
def get_analytics_suggestions(
    user_id: uuid.UUID = Depends(get_current_user_id),
):
    """
    Returns curated, high-value analytical questions with expected chart types.
    """
    return NaturalLanguageAnalyticsService.get_suggestions()


@nl_analytics_router.post(
    "/saved",
    response_model=SavedAnalyticsQueryRead,
    status_code=status.HTTP_201_CREATED,
    summary="Save an analytics query",
)
def save_analytics_query(
    payload: SavedAnalyticsQueryCreate,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """
    Saves an analytics query and plan snapshot for quick re-execution.
    """
    return NaturalLanguageAnalyticsService.save_query(
        db=db,
        user_id=user_id,
        payload=payload,
    )


@nl_analytics_router.get(
    "/saved",
    response_model=SavedAnalyticsQueryListResponse,
    summary="List saved analytics queries",
)
def list_saved_queries(
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """
    Retrieves all saved queries for the authenticated user.
    """
    records = NaturalLanguageAnalyticsService.list_saved_queries(db=db, user_id=user_id)
    return SavedAnalyticsQueryListResponse(queries=records, total=len(records))


@nl_analytics_router.delete(
    "/saved/{query_id}",
    summary="Delete a saved query",
)
def delete_saved_query(
    query_id: uuid.UUID,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """
    Deletes a saved query strictly scoped to the user.
    """
    success = NaturalLanguageAnalyticsService.delete_saved_query(
        db=db,
        user_id=user_id,
        query_id=query_id,
    )
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Saved query not found or access denied.",
        )
    return {"status": "deleted", "query_id": str(query_id)}


@nl_analytics_router.get(
    "/export",
    summary="Export query analytical records",
)
def export_query_records(
    query: str = Query(..., description="Query to execute and export"),
    format: str = Query("json", pattern="^(json|csv)$", description="Export format: json or csv"),
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """
    Executes an analytical query and exports supporting records as JSON or CSV.
    """
    try:
        req = AnalyticsQueryRequest(query=query)
        resp = NaturalLanguageAnalyticsService.execute_query(db=db, user_id=user_id, request=req)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )

    if format == "csv":
        output = io.StringIO()
        records = resp.supporting_records
        if records:
            writer = csv.DictWriter(output, fieldnames=list(records[0].keys()))
            writer.writeheader()
            writer.writerows(records)
        return Response(
            content=output.getvalue(),
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename=analytics_export_{uuid.uuid4().hex[:6]}.csv"},
        )
    else:
        return Response(
            content=json.dumps(resp.supporting_records, indent=2, default=str),
            media_type="application/json",
            headers={"Content-Disposition": f"attachment; filename=analytics_export_{uuid.uuid4().hex[:6]}.json"},
        )
