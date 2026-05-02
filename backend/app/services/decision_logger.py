"""Persist structured agent I/O to `agent_logs` for explainability."""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.models.agent_log import AgentLog


class DecisionLogger:
    def __init__(self, db: Session) -> None:
        self._db = db

    def log(
        self,
        *,
        agent_name: str,
        action: str,
        input_payload: dict[str, Any] | None,
        output_payload: dict[str, Any] | None,
        inventory_decision_id: int | None = None,
        triggered_by_user_id: int | None = None,
        triggered_by_role: str | None = None,
    ) -> AgentLog:
        row = AgentLog(
            agent_name=agent_name,
            action=action,
            input_payload=input_payload,
            output_payload=output_payload,
            inventory_decision_id=inventory_decision_id,
            triggered_by_user_id=triggered_by_user_id,
            triggered_by_role=triggered_by_role,
        )
        self._db.add(row)
        self._db.flush()
        return row
