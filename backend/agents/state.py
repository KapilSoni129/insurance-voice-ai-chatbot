from typing import TypedDict, Literal, Optional


class AgentState(TypedDict):
    call_id: str
    caller_phone: Optional[str]

    # Authentication
    auth_status: Literal["pending", "authenticated", "failed", "not_found"]
    auth_attempts: int
    customer_name: Optional[str]
    account_id: Optional[str]

    # Claims
    claim_status: Optional[str]
    claim_details: Optional[dict]

    # Routing
    current_agent: Literal["supervisor", "auth", "claims", "faq", "escalation"]
    tool_name: Optional[str]
    tool_params: Optional[dict]

    # FAQ
    faq_answer: Optional[str]

    # Escalation
    escalation_reason: Optional[str]

    # Post-call
    resolution: Optional[Literal["resolved", "escalated", "unresolved"]]
    agents_used: list[str]
