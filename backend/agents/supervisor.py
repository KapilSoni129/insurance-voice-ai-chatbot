import logging
from backend.agents.state import AgentState

logger = logging.getLogger(__name__)


def supervisor_node(state: AgentState) -> dict:
    """Route to the correct agent based on the incoming tool call from Vapi."""
    tool_name = state.get("tool_name")

    routing = {
        "authenticate_customer": "auth",
        "get_claim_status": "claims",
        "search_faq": "faq",
        "escalate_call": "escalation",
    }

    agent = routing.get(tool_name, "supervisor")
    logger.info(f"[SUPERVISOR] {tool_name} → {agent}")
    return {"current_agent": agent}


def route_from_supervisor(state: AgentState) -> str:
    agent = state.get("current_agent", "supervisor")
    if agent == "auth":
        return "auth_agent"
    elif agent == "claims":
        return "claims_agent"
    elif agent == "faq":
        return "faq_agent"
    elif agent == "escalation":
        return "escalation_agent"
    return "end"
