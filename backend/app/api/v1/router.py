from fastapi import APIRouter

from app.api.v1.health import router as health_router
from app.api.v1.users import router as users_router
from app.api.v1.tasks import router as tasks_router
from app.api.v1.interruptions import router as interruptions_router
from app.api.v1.locations import router as locations_router
from app.api.v1.analytics import router as analytics_router
from app.api.v1.predictions import router as predictions_router
from app.api.v1.recommendations import router as recommendations_router
from app.api.v1.privacy import router as privacy_router
from app.api.v1.telemetry import router as telemetry_router
from app.api.v1.context import router as context_router
from app.api.v1.adaptive import router as adaptive_router
from app.api.v1.integrations import router as integrations_router
from app.api.v1.google_integrations import router as google_integrations_router
from app.api.v1.microsoft_integrations import router as microsoft_integrations_router
from app.api.v1.scheduling import router as scheduling_router
from app.api.v1.devices import router as devices_router
from app.api.v1.activity import router as activity_router
from app.api.v1.causal import router as causal_router
from app.api.v1.counterfactual import router as counterfactual_router
from app.api.v1.sequence_prediction import router as sequence_router

api_router = APIRouter()

api_router.include_router(health_router)
api_router.include_router(users_router)
api_router.include_router(tasks_router)
api_router.include_router(interruptions_router)
api_router.include_router(locations_router)
api_router.include_router(analytics_router)
api_router.include_router(predictions_router)
api_router.include_router(recommendations_router)
api_router.include_router(privacy_router)
api_router.include_router(telemetry_router)
api_router.include_router(context_router)
api_router.include_router(adaptive_router)
api_router.include_router(google_integrations_router)
api_router.include_router(microsoft_integrations_router)
api_router.include_router(integrations_router)
api_router.include_router(scheduling_router)
api_router.include_router(devices_router)
api_router.include_router(activity_router)
api_router.include_router(causal_router)
api_router.include_router(counterfactual_router)
api_router.include_router(sequence_router)

