"""Aggregates domain routers. Auth is per-route (no global dependency) so public /auth/* stays unauthenticated."""

from fastapi import APIRouter

from app.config import get_settings
from app.routes import (
    agent_logs,
    analytics,
    auth,
    business,
    evaluation,
    forecast,
    inventory,
    products,
    sales,
    simulation,
    users,
)

api_router = APIRouter()
# Auth first: public register/login + protected /me; rate limiter uses app.state.limiter.
api_router.include_router(auth.router)
api_router.include_router(users.router)
api_router.include_router(business.router)
api_router.include_router(analytics.router)
api_router.include_router(sales.router, tags=["sales"])
api_router.include_router(forecast.router, tags=["forecast"])
api_router.include_router(inventory.router, tags=["inventory"])
api_router.include_router(evaluation.router, tags=["evaluation"])
api_router.include_router(products.router, tags=["products"])
api_router.include_router(agent_logs.router, tags=["agent-logs"])
api_router.include_router(simulation.router, tags=["simulation"])

if get_settings().debug:
    from app.routes import debug_internal

    api_router.include_router(debug_internal.router, tags=["debug-internal"])
