from pydantic import BaseModel


class AgentLogRead(BaseModel):
    id: int
    agent_name: str
    action: str
    created_at: str
    input_payload: dict | None
    output_payload: dict | None
    inventory_decision_id: int | None
    triggered_by_user_id: int | None = None
    triggered_by_role: str | None = None
    triggered_by_email: str | None = None


class AgentLogListResponse(BaseModel):
    logs: list[AgentLogRead]
