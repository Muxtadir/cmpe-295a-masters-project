"""Audit trail listing with filters (SKU, user, agent type)."""

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps.auth import require_store_manager_or_admin
from app.models.agent_log import AgentLog
from app.models.user import User
from app.schemas.agent_logs import AgentLogListResponse, AgentLogRead

router = APIRouter()


@router.get("/agent-logs", response_model=AgentLogListResponse)
def list_agent_logs(
    current: Annotated[
        User,
        Depends(require_store_manager_or_admin),
    ],
    sku: str | None = Query(default=None, max_length=64),
    agent_type: str | None = Query(default=None, max_length=64),
    user_id: int | None = Query(default=None, ge=1),
    db: Session = Depends(get_db),
) -> AgentLogListResponse:
    stmt = (
        select(AgentLog, User.email)
        .outerjoin(User, AgentLog.triggered_by_user_id == User.id)
        .order_by(AgentLog.created_at.desc())
    )
    if agent_type:
        stmt = stmt.where(AgentLog.agent_name.ilike(f"%{agent_type}%"))
    if sku:
        stmt = stmt.where(
            or_(
                AgentLog.input_payload["sku"].astext == sku,
                AgentLog.output_payload["sku"].astext == sku,
            )
        )
    if user_id is not None:
        stmt = stmt.where(AgentLog.triggered_by_user_id == user_id)

    rows = db.execute(stmt.limit(200)).all()

    return AgentLogListResponse(
        logs=[
            AgentLogRead(
                id=log.id,
                agent_name=log.agent_name,
                action=log.action,
                created_at=log.created_at.isoformat(),
                input_payload=log.input_payload,
                output_payload=log.output_payload,
                inventory_decision_id=log.inventory_decision_id,
                triggered_by_user_id=log.triggered_by_user_id,
                triggered_by_role=log.triggered_by_role,
                triggered_by_email=email,
            )
            for log, email in rows
        ]
    )
