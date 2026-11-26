"""
API Router for Intelligent Project Progress Forecasting (Phase 8.6).
"""
from __future__ import annotations

import uuid
from typing import Optional

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.core.deps import get_current_user_id
from app.db.session import get_db
from app.models.project_forecast import ForecastingModelType
from app.schemas.project_forecast import (
    ForecastScenarioRequest,
    ForecastScenarioResult,
    ModelBenchmarkResult,
    ProjectForecastDashboardData,
    ProjectForecastGenerateRequest,
    ProjectForecastRead,
)
from app.services.project_forecast_service import ProjectForecastService

forecasts_router = APIRouter(prefix="/forecasts", tags=["project-forecasting"])


@forecasts_router.get(
    "/projects/{project_id}",
    response_model=ProjectForecastDashboardData,
    summary="Get project forecast dashboard data",
)
def get_project_forecast_dashboard(
    project_id: uuid.UUID,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """Retrieves current probabilistic forecast, milestone predictions, and delay contributors for a project."""
    return ProjectForecastService.get_forecast_dashboard(db, user_id, project_id)


@forecasts_router.post(
    "/projects/{project_id}/generate",
    response_model=ProjectForecastRead,
    status_code=status.HTTP_201_CREATED,
    summary="Generate fresh project progress forecast",
)
def generate_project_forecast(
    project_id: uuid.UUID,
    payload: Optional[ProjectForecastGenerateRequest] = None,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """
    Computes a fresh probabilistic forecast (P10/P50/P90 intervals, on-time probability,
    and delay contributors) using leakage-safe historical evidence.
    """
    req = payload or ProjectForecastGenerateRequest(project_id=project_id)
    req.project_id = project_id
    forecast = ProjectForecastService.generate_project_forecast(db, user_id, req)
    return ProjectForecastRead.model_validate(forecast)


@forecasts_router.post(
    "/projects/{project_id}/scenario",
    response_model=ForecastScenarioResult,
    summary="Simulate what-if counterfactual scenario",
)
def run_scenario_simulation(
    project_id: uuid.UUID,
    payload: ForecastScenarioRequest,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """
    Simulates counterfactual what-if adjustments:
    - Prioritizing overdue deliverables.
    - Adding weekly focus hours.
    - Resolving blocked dependencies.
    - Modifying project deadline.
    """
    payload.project_id = project_id
    return ProjectForecastService.run_scenario_simulation(db, user_id, payload)


@forecasts_router.get(
    "/benchmark",
    response_model=ModelBenchmarkResult,
    summary="Evaluate and benchmark forecasting models",
)
def get_model_benchmarks(
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """Compares MAE, RMSE, Brier score, and prediction interval coverage across forecasting models."""
    return ProjectForecastService.benchmark_models(db, user_id)
